"""The fact line: a fact the agent states, with the policy section it rests on, rendered from the tool results and
said right after the agent's answer (review of the model comparison, 2026-10-24).

The instructions ask for a citation whenever an answer rests on the policy, and the tool results put the section
beside the fact; in the runs of 2026-10-23 the agent still told a refund paid before the conversation without the
section on refunding each unit once (D20, Luna none, tries 1 and 2), and an order's shipped status without the
section on which orders qualify (D35 try 2, both models). For these two facts the line is written from the records,
not by the model, and only when the agent's answer states the fact and no answer of the conversation has cited the
section yet:

- remaining: the answer gives the receipt number of a refund a tool showed as paid, and not paid in this conversation;
- eligible-orders: the answer names the status of an order a tool showed as not delivered (shipped, processing,
  invoiced or unavailable; "approved", "created" and "canceled" are left out, since the same words tell of proposals).

The graph says the line as its own message after an answer with no tool calls, so the customer, the model and the
evaluator see the same words; the message is marked, and the diagnostics count the citations it carries apart from
the model's own.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from refund_agent.policy import Policy

STATUS_WORDS = ("shipped", "processing", "invoiced", "unavailable")


def _tool_facts(history: Sequence[dict]) -> tuple[dict[str, None], set[str], dict[str, str]]:
    """Receipts shown as paid (in order), receipts paid in this conversation, and the not-delivered orders' statuses."""
    shown: dict[str, None] = {}
    paid_here: set[str] = set()
    on_its_way: dict[str, str] = {}
    for message in history:
        if message.get("role") != "tool":
            continue
        try:
            result = json.loads(message.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(result, dict):
            continue
        if message.get("name") == "execute_refund":
            receipt = result.get("receipt") or {}
            if isinstance(receipt, dict) and receipt.get("receipt_number"):
                paid_here.add(receipt["receipt_number"])
            continue
        found = list(result.get("orders") or [])
        if isinstance(result.get("order"), dict):
            found.append(result["order"])
        for order in found:
            if not isinstance(order, dict):
                continue
            if order.get("status") in STATUS_WORDS:
                on_its_way[order["order_id"]] = order["status"]
            for request in order.get("requests") or []:
                if isinstance(request, dict) and request.get("receipt_number"):
                    shown[request["receipt_number"]] = None
        request = result.get("request")
        if isinstance(request, dict) and isinstance(request.get("receipt"), dict):
            number = request["receipt"].get("receipt_number")
            if number:
                shown[number] = None
    return shown, paid_here, on_its_way


def fact_line(history: Sequence[dict], answer: str, policy: Policy) -> str:
    """The line to say after the agent's answer, or "" when none is due. history: the conversation's messages before
    the answer, as the graph keeps them."""
    said_before = " ".join(m.get("text") or "" for m in history if m.get("role") == "agent")
    shown, paid_here, on_its_way = _tool_facts(history)
    sentences = []
    remaining = policy.citation("remaining")
    if remaining not in answer and remaining not in said_before:
        receipts = [r for r in shown if r not in paid_here and r in answer]
        if receipts:
            sentences.append(
                f"The refund with receipt {', '.join(receipts)} is already paid, and each unit is refunded only once, "
                f"so those units cannot be refunded again ({remaining})."
            )
    eligible = policy.citation("eligible-orders")
    if eligible not in answer and eligible not in said_before:
        named = [
            (order_id, status)
            for order_id, status in on_its_way.items()
            if re.search(rf"\b{status}\b", answer, re.IGNORECASE)
        ]
        if named:
            orders = ", ".join(f"order {order_id} is {status}" for order_id, status in named)
            sentences.append(
                f"Only orders recorded as delivered can be refunded through this process, and {orders} ({eligible})."
            )
    return " ".join(sentences)
