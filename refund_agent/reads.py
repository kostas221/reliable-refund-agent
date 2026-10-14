"""What the screens and the agent read (plan section 8): orders, the proposal card, a conversation, the staff queue.

Reads never change anything. A proposal that is still open in the database but whose validity has passed is shown
as expired (display_status), because the stored status changes only when the next action touches it. Text written
by customers, sellers or the model is returned under keys ending in "_untrusted" or under "untrusted", and the
screens must show it as plain text, apart from the fields the backend computed (plan section 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, RowMapping, text

OPEN_STATUSES = ("awaiting_customer_confirmation", "awaiting_staff_approval", "approved")


def _rows(conn: Connection, sql: str, **params: Any) -> list[RowMapping]:
    return list(conn.execute(text(sql), params).mappings())


def _one(conn: Connection, sql: str, **params: Any) -> RowMapping | None:
    return conn.execute(text(sql), params).mappings().first()


def orders(conn: Connection, customer_id: str, currency: str) -> list[dict]:
    """The customer's orders with their units, so the customer can pick the item to refund."""
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
            }
        )
    return result


def _display_status(proposal: RowMapping, now: datetime) -> str:
    if proposal["status"] in OPEN_STATUSES and now >= proposal["expires_at"]:
        return "expired"
    return proposal["status"]


def proposal_card(conn: Connection, proposal: RowMapping, now: datetime) -> dict:
    """The fields the backend computed and stored; the receipt only once a refund is committed."""
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
    }


def conversation(conn: Connection, conversation_id: str, now: datetime) -> dict | None:
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
        "SELECT author, content_untrusted, created_at FROM messages WHERE conversation_id = :c ORDER BY created_at, id",
        c=conversation_id,
    )
    return {
        "conversation_id": found["id"],
        "customer_id": found["customer_id"],
        "control": found["control"],
        "proposals": [proposal_card(conn, p, now) for p in proposals],
        "handoffs": [dict(h) for h in handoffs],
        "messages": [
            {"author": m["author"], "content_untrusted": m["content_untrusted"], "at": m["created_at"]}
            for m in messages
        ],
    }


def staff_proposal(conn: Connection, proposal: RowMapping, now: datetime) -> dict:
    """The approval screen: the backend's fields apart from text nobody verified (plan section 7)."""
    customer = _one(conn, "SELECT id, display_name, email FROM users WHERE id = :u", u=proposal["customer_id"])
    order = _one(conn, "SELECT seller_message_untrusted FROM orders WHERE id = :o", o=proposal["order_id"])
    confirmation = _one(
        conn, "SELECT decision, decided_at FROM customer_confirmations WHERE proposal_id = :p", p=proposal["id"]
    )
    return {
        "trusted": {
            **proposal_card(conn, proposal, now),
            "customer": dict(customer),
            "customer_confirmed_at": confirmation["decided_at"] if confirmation else None,
        },
        "untrusted": {
            "agent_summary": proposal["summary_untrusted"],
            "seller_message": order["seller_message_untrusted"],
        },
    }


def staff_queue(conn: Connection, now: datetime) -> dict:
    waiting = _rows(
        conn, "SELECT * FROM proposals WHERE status = 'awaiting_staff_approval' ORDER BY created_at, created_xact"
    )
    handoffs = _rows(
        conn,
        "SELECT h.*, c.customer_id FROM handoffs h JOIN conversations c ON c.id = h.conversation_id "
        "WHERE h.status = 'open' ORDER BY h.created_at",
    )
    return {
        "awaiting_approval": [staff_proposal(conn, p, now) for p in waiting],
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
