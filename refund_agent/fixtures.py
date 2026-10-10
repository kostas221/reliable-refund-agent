"""Load a scenario's initial state into a database, as refund_owner (the application role cannot write order facts).

Earlier refunds and proposals of the fixture become ordinary rows, in a history conversation of the customer, so
the services see them exactly as if they had happened through the flow.
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import Connection, Engine, text

from refund_agent.policy import Policy
from refund_agent.refunds import _digest, proposal_content_hash
from refund_agent.scenarios import Scenario


def _insert(conn: Connection, table: str, **values: object) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join(f":{name}" for name in values)
    conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"), values)


def seed(engine: Engine, scenario: Scenario, policy: Policy) -> None:
    fixture = scenario.fixture
    with engine.begin() as conn:
        for person in fixture.customers:
            _insert(conn, "users", id=person.id, role="customer", email=person.email, display_name=person.name)
        for person in fixture.staff:
            _insert(conn, "users", id=person.id, role="staff", email=person.email, display_name=person.name)
        for order in fixture.orders:
            _insert(
                conn,
                "orders",
                id=order.id,
                customer_id=order.customer,
                status=order.status,
                purchased_at=order.purchased_at,
                delivered_at=order.delivered_at,
                material_version=1,
                source="synthetic",
                seller_message_untrusted=order.seller_message_untrusted,
            )
            for number, unit in enumerate(order.units, start=1):
                _insert(
                    conn,
                    "order_units",
                    id=unit.id,
                    order_id=order.id,
                    unit_no=number,
                    product_name=unit.product,
                    price_minor=unit.price_minor,
                    paid_minor=unit.paid_minor,
                    shipping_minor=unit.shipping_minor,
                    received_back_at=unit.received_back_at,
                )
            for number, payment in enumerate(order.payments, start=1):
                _insert(
                    conn,
                    "payments",
                    id=f"{order.id}-p{number}",
                    order_id=order.id,
                    sequential=number,
                    method=payment.method,
                    installments=payment.installments,
                    amount_minor=payment.amount_minor,
                )
        _seed_history(conn, scenario, policy)


def _seed_history(conn: Connection, scenario: Scenario, policy: Policy) -> None:
    fixture = scenario.fixture
    order_of_unit, units = fixture.order_of_unit(), fixture.unit_by_id()
    history = [
        (f"{scenario.id.lower()}-r{n}", r.units, r.committed_at, "refunded", r)
        for n, r in enumerate(fixture.past_refunds, start=1)
    ]
    history += [(p.id, p.units, p.created_at, p.status, None) for p in fixture.past_proposals]
    conversations: set[str] = set()
    for proposal_id, unit_ids, created_at, status, refund in history:
        order = order_of_unit[unit_ids[0]]
        conversation_id = f"{order.customer}-history"
        if conversation_id not in conversations:
            _insert(
                conn,
                "conversations",
                id=conversation_id,
                customer_id=order.customer,
                control="agent",
                created_at=min(h[2] for h in history),
            )
            conversations.add(conversation_id)
        payment_id = f"{order.id}-p1" if len(order.payments) == 1 else None
        amounts = [(unit_id, units[unit_id].paid_minor) for unit_id in unit_ids]
        amount = sum(paid for _, paid in amounts)
        expires_at = created_at + timedelta(hours=policy.rules.proposal_ttl_hours)
        content_hash = proposal_content_hash(
            customer_id=order.customer,
            order_id=order.id,
            units=amounts,
            amount_minor=amount,
            currency=policy.currency,
            payment_id=payment_id,
            policy_version=policy.version,
            policy_hash=policy.content_hash(),
            order_material_version=1,
            expires_at=expires_at,
        )
        _insert(
            conn,
            "proposals",
            id=proposal_id,
            request_key=f"history-{proposal_id}",
            request_hash=_digest({"history": proposal_id}),
            conversation_id=conversation_id,
            customer_id=order.customer,
            order_id=order.id,
            payment_id=payment_id,
            amount_minor=amount,
            currency=policy.currency,
            policy_version=policy.version,
            policy_hash=policy.content_hash(),
            order_material_version=1,
            status=status,
            status_reason=None if refund else status,
            created_at=created_at,
            expires_at=expires_at,
            content_hash=content_hash,
        )
        for unit_id, paid in amounts:
            _insert(conn, "proposal_units", proposal_id=proposal_id, order_unit_id=unit_id, amount_minor=paid)
        if refund is None:
            continue
        staff_id = fixture.staff[0].id
        _insert(
            conn,
            "customer_confirmations",
            id=f"{proposal_id}-conf",
            proposal_id=proposal_id,
            customer_id=order.customer,
            decision="confirmed",
            content_hash=content_hash,
            decided_at=created_at,
        )
        _insert(
            conn,
            "staff_decisions",
            id=f"{proposal_id}-dec",
            proposal_id=proposal_id,
            staff_id=staff_id,
            decision="approved",
            content_hash=content_hash,
            decided_at=created_at,
        )
        receipt = {
            "receipt_number": refund.receipt_number,
            "operation_id": f"{proposal_id}-op",
            "proposal_id": proposal_id,
            "amount_minor": amount,
            "currency": policy.currency,
            "payment_id": payment_id,
            "units": [{"unit_id": u, "amount_minor": a} for u, a in amounts],
            "committed_at": created_at.isoformat(),
        }
        conn.execute(
            text(
                "INSERT INTO refund_operations (id, proposal_id, approval_id, approval_decision, idempotency_key, "
                "request_hash, amount_minor, currency, payment_id, receipt_number, receipt, committed_at) VALUES "
                "(:id, :proposal, :approval, 'approved', :key, :hash, :amount, :currency, :payment, :number, "
                "CAST(:receipt AS jsonb), :at)"
            ),
            {
                "id": f"{proposal_id}-op",
                "proposal": proposal_id,
                "approval": f"{proposal_id}-dec",
                "key": f"history-{proposal_id}",
                "hash": _digest({"proposal": proposal_id}),
                "amount": amount,
                "currency": policy.currency,
                "payment": payment_id,
                "number": refund.receipt_number,
                "receipt": json.dumps(receipt),
                "at": created_at,
            },
        )
        for unit_id, paid in amounts:
            _insert(
                conn,
                "ledger_lines",
                id=f"{proposal_id}-{unit_id}",
                operation_id=f"{proposal_id}-op",
                order_unit_id=unit_id,
                amount_minor=paid,
                currency=policy.currency,
                payment_id=payment_id,
            )
