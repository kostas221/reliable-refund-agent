"""What the screens and the agent read (plan section 8): orders with their requests, the proposal card, a conversation,
the staff queue and a conversation's history.

Reads never change anything. A proposal that is still open in the database but whose validity has passed is shown
as expired (display_status), because the stored status changes only when the next action touches it. Text written
by customers, sellers or the model is returned under keys ending in "_untrusted" or under "untrusted", and the
screens must show it as plain text, apart from the fields the backend computed (plan section 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, RowMapping, text

from refund_agent.policy import Policy

OPEN_STATUSES = ("awaiting_customer_confirmation", "awaiting_staff_approval", "approved")
# What the history may show of an audit event's details: values the backend set, never free text (a handoff's
# reason can be the model's words, and is shown apart, as untrusted).
HISTORY_DETAILS = ("status", "reasons", "decision", "handoff_id", "origin")


def _rows(conn: Connection, sql: str, **params: Any) -> list[RowMapping]:
    return list(conn.execute(text(sql), params).mappings())


def _one(conn: Connection, sql: str, **params: Any) -> RowMapping | None:
    return conn.execute(text(sql), params).mappings().first()


def orders(conn: Connection, customer_id: str, currency: str, now: datetime) -> list[dict]:
    """The customer's orders with their units, so the customer can pick the item to refund, and the requests already
    made for each order, so the customer and the agent see the same history."""
    result = []
    for order in _rows(
        conn,
        "SELECT id, status, purchased_at, delivered_at FROM orders WHERE customer_id = :c ORDER BY purchased_at DESC",
        c=customer_id,
    ):
        units = _rows(
            conn,
            "SELECT u.id, u.unit_no, u.product_name, u.paid_minor, u.received_back_at IS NOT NULL AS received_back, "
            "EXISTS (SELECT 1 FROM ledger_lines l WHERE l.order_unit_id = u.id) AS refunded "
            "FROM order_units u WHERE u.order_id = :o ORDER BY u.unit_no",
            o=order["id"],
        )
        result.append(
            {
                "order_id": order["id"],
                "status": order["status"],
                "purchased_at": order["purchased_at"],
                "delivered_at": order["delivered_at"],
                "currency": currency,
                "units": [
                    {
                        "unit_id": u["id"],
                        "product": u["product_name"],
                        "paid_minor": u["paid_minor"],
                        "received_back": u["received_back"],
                        "refunded": u["refunded"],
                    }
                    for u in units
                ],
                "requests": _requests(conn, customer_id, order["id"], now),
            }
        )
    return result


def _requests(conn: Connection, customer_id: str, order_id: str, now: datetime) -> list[dict]:
    """Every proposal for this order, oldest first: what was asked, what became of it, and the receipt if paid. No
    amount for a request the policy refused, as when it was proposed: there is nothing to promise."""
    result = []
    for proposal in _rows(
        conn,
        "SELECT * FROM proposals WHERE customer_id = :c AND order_id = :o ORDER BY created_at, created_xact",
        c=customer_id,
        o=order_id,
    ):
        units = conn.execute(
            text("SELECT order_unit_id FROM proposal_units WHERE proposal_id = :p ORDER BY order_unit_id"),
            {"p": proposal["id"]},
        ).scalars()
        operation = _one(conn, "SELECT receipt FROM refund_operations WHERE proposal_id = :p", p=proposal["id"])
        result.append(
            {
                "proposal_id": proposal["id"],
                "status": _display_status(proposal, now),
                "amount_minor": None if proposal["status"] == "ineligible" else proposal["amount_minor"],
                "unit_ids": list(units),
                "created_at": proposal["created_at"],
                "receipt_number": operation["receipt"]["receipt_number"] if operation else None,
                "rejection_reason": _rejection_reason(conn, proposal["id"]),
            }
        )
    return result


def conversations(conn: Connection, customer_id: str) -> list[dict]:
    """The customer's conversations, the latest activity first, so a screen finds them again after a refresh."""
    return [
        dict(row)
        for row in _rows(
            conn,
            "SELECT c.id AS conversation_id, c.control, c.created_at, max(m.created_at) AS last_message_at "
            "FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id WHERE c.customer_id = :c "
            "GROUP BY c.id ORDER BY coalesce(max(m.created_at), c.created_at) DESC, c.id",
            c=customer_id,
        )
    ]


def _citations(proposal: RowMapping, policy: Policy) -> list[dict]:
    """The policy sections behind a refusal or a handoff, with the ID a citation of each carries (INV-10)."""
    same_version = proposal["policy_version"] == policy.version
    return [
        {
            "citation": f"{policy.policy_id}/{proposal['policy_version']}/{reason}",
            "title": policy.section(reason).title if same_version else None,
        }
        for reason in proposal["reasons"]
    ]


def _rejection_reason(conn: Connection, proposal_id: str) -> str | None:
    """What the staff member told the customer when rejecting; None for any other decision or none yet."""
    return conn.execute(
        text("SELECT reason FROM staff_decisions WHERE proposal_id = :p AND decision = 'rejected'"), {"p": proposal_id}
    ).scalar()


def _display_status(proposal: RowMapping, now: datetime) -> str:
    if proposal["status"] in OPEN_STATUSES and now >= proposal["expires_at"]:
        return "expired"
    return proposal["status"]


def proposal_card(conn: Connection, proposal: RowMapping, now: datetime, policy: Policy) -> dict:
    """The fields the backend computed and stored, the citations of the sections behind a refusal or a handoff, and
    the receipt only once a refund is committed."""
    units = _rows(
        conn,
        "SELECT pu.order_unit_id, u.product_name, pu.amount_minor FROM proposal_units pu "
        "JOIN order_units u ON u.id = pu.order_unit_id WHERE pu.proposal_id = :p ORDER BY pu.order_unit_id",
        p=proposal["id"],
    )
    operation = _one(conn, "SELECT receipt FROM refund_operations WHERE proposal_id = :p", p=proposal["id"])
    return {
        "proposal_id": proposal["id"],
        "conversation_id": proposal["conversation_id"],
        "order_id": proposal["order_id"],
        "status": proposal["status"],
        "display_status": _display_status(proposal, now),
        "status_reason": proposal["status_reason"],
        "policy_reasons": list(proposal["reasons"]),
        "policy_citations": _citations(proposal, policy),
        "policy_version": proposal["policy_version"],
        "amount_minor": proposal["amount_minor"],
        "currency": proposal["currency"],
        "units": [
            {"unit_id": u["order_unit_id"], "product": u["product_name"], "amount_minor": u["amount_minor"]}
            for u in units
        ],
        "created_at": proposal["created_at"],
        "expires_at": proposal["expires_at"],
        "receipt": operation["receipt"] if operation else None,
        "rejection_reason": _rejection_reason(conn, proposal["id"]),
    }


def conversation(conn: Connection, conversation_id: str, now: datetime, policy: Policy) -> dict | None:
    found = _one(conn, "SELECT * FROM conversations WHERE id = :c", c=conversation_id)
    if found is None:
        return None
    proposals = _rows(conn, "SELECT * FROM proposals WHERE conversation_id = :c ORDER BY created_at", c=conversation_id)
    handoffs = _rows(
        conn,
        "SELECT id, origin, status, created_at FROM handoffs WHERE conversation_id = :c ORDER BY created_at",
        c=conversation_id,
    )
    messages = _rows(
        conn,
        "SELECT author, content_untrusted, created_at FROM messages WHERE conversation_id = :c ORDER BY seq",
        c=conversation_id,
    )
    return {
        "conversation_id": found["id"],
        "customer_id": found["customer_id"],
        "control": found["control"],
        "proposals": [proposal_card(conn, p, now, policy) for p in proposals],
        "handoffs": [dict(h) for h in handoffs],
        "messages": [
            {"author": m["author"], "content_untrusted": m["content_untrusted"], "at": m["created_at"]}
            for m in messages
        ],
    }


def staff_proposal(conn: Connection, proposal: RowMapping, now: datetime, policy: Policy) -> dict:
    """The approval screen: the backend's fields apart from text nobody verified (plan section 7)."""
    customer = _one(conn, "SELECT id, display_name, email FROM users WHERE id = :u", u=proposal["customer_id"])
    order = _one(conn, "SELECT seller_message_untrusted FROM orders WHERE id = :o", o=proposal["order_id"])
    confirmation = _one(
        conn, "SELECT decision, decided_at FROM customer_confirmations WHERE proposal_id = :p", p=proposal["id"]
    )
    return {
        "trusted": {
            **proposal_card(conn, proposal, now, policy),
            "customer": dict(customer),
            "customer_confirmed_at": confirmation["decided_at"] if confirmation else None,
        },
        "untrusted": {
            "agent_summary": proposal["summary_untrusted"],
            "seller_message": order["seller_message_untrusted"],
        },
    }


def staff_queue(conn: Connection, now: datetime, policy: Policy) -> dict:
    waiting = _rows(
        conn, "SELECT * FROM proposals WHERE status = 'awaiting_staff_approval' ORDER BY created_at, created_xact"
    )
    handoffs = _rows(
        conn,
        "SELECT h.*, c.customer_id FROM handoffs h JOIN conversations c ON c.id = h.conversation_id "
        "WHERE h.status = 'open' ORDER BY h.created_at",
    )
    # A decision the agent has not been told of, after a failed delivery: shown until a delivery succeeds, so a
    # request cannot wait unseen once the delivery's attempts run out (review of 2026-10-19, R1).
    untold = _rows(
        conn,
        "SELECT proposal_id, conversation_id, decision, attempts, last_error FROM agent_notices "
        "WHERE delivered_at IS NULL AND last_error IS NOT NULL ORDER BY created_at, id",
    )
    return {
        "awaiting_approval": [staff_proposal(conn, p, now, policy) for p in waiting],
        "untold_decisions": [dict(n) for n in untold],
        "open_handoffs": [
            {
                "trusted": {
                    "handoff_id": h["id"],
                    "conversation_id": h["conversation_id"],
                    "customer_id": h["customer_id"],
                    "origin": h["origin"],  # as recorded; "customer" from the agent's tool is the agent's claim
                    "created_at": h["created_at"],
                    "pending_proposal_id": h["pending_proposal_id"],
                    "prior_actions": h["prior_actions"],
                },
                "untrusted": {
                    "reason": h["reason"],  # written by whoever asked for the handoff, possibly the model
                    "customer_goal": h["customer_goal_untrusted"],
                    "confirmed_facts": h["confirmed_facts_untrusted"],
                    "decision_needed": h["decision_needed_untrusted"],
                },
            }
            for h in handoffs
        ],
    }


def history(conn: Connection, conversation_id: str) -> list[dict]:
    """The audit log of a conversation and its proposals, oldest first, for the staff screen: who did what, and
    whether it was committed or refused, and why. Only the backend's own values of each event's details."""
    events = _rows(
        conn,
        "SELECT at, actor_type, actor_id, event, outcome, reason, proposal_id, operation_id, details FROM audit_events "
        "WHERE conversation_id = :c OR proposal_id IN (SELECT id FROM proposals WHERE conversation_id = :c) "
        "ORDER BY at, id",
        c=conversation_id,
    )
    return [
        {
            **{key: event[key] for key in event.keys() if key != "details"},
            "details": {key: value for key, value in (event["details"] or {}).items() if key in HISTORY_DETAILS},
        }
        for event in events
    ]
