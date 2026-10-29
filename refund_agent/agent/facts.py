"""The fact line: a fact the agent states, with the policy section it rests on, rendered from the tool results and
said right after the agent's answer (review of the model comparison, 2026-10-24).

The instructions ask for a citation whenever an answer rests on the policy, and the tool results put the section
beside the fact; in the runs of 2026-10-23 the agent still told a refund paid before the conversation without the
section on refunding each unit once (D20, Luna none, tries 1 and 2), and an order's shipped status without the
section on which orders qualify (D35 try 2, both models). For these facts the line is written from the records, not
by the model, and only when the agent's answer states the fact and no answer of the conversation has cited the
section yet:

- remaining: the answer gives the receipt number of a refund a tool showed as paid, and not paid in this conversation;
- eligible-orders: the answer names the status of an order a tool showed as not delivered (shipped, processing,
  invoiced or unavailable; "approved", "created" and "canceled" are left out, since the same words tell of proposals).
  Each order counts with its latest read, and a result that holds no order replaces nothing. When the answer names
  orders, by their ID or by a word of their products that no other order in view has, only those count; an answer
  that names none counts for every order whose status it states ("Your order is shipped"). So "Your scanner was shipped
  back to us" says nothing of another order on its way (review of 2026-10-28);
- a handoff's sections: a handoff was made, and the sections its result gave are not cited yet (final evaluation of
  v1.1, 2026-10-26: all 98 required refusal citations of the runs on policy v2 were shown, since a refusal's result
  gives its sections; a handoff's result gave none, and 11 of 18 required handoff citations were missed). Only the
  sections not cited yet are said, after the agent's announcement.

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
_WORD = re.compile(r"[a-z]{3,}")  # a word of a product's name, as the answer may use it
# Why a person takes over, by the handoff's reason code, in words for the customer.
HANDOFF_CASES = {
    "customer_asked": "A person takes over whenever you ask for one",
    "shop_decided": "Under the policy, a staff member decides this request",
    "return_disputed": "A staff member reviews units you say were sent but are not recorded as received back",
    "delivery_disputed": "A staff member reviews an order recorded as delivered that you say never arrived",
    "shipping_refund": "A staff member reviews a request to refund the shipping charge",
}


def _handoffs(history: Sequence[dict]) -> list[tuple[str, list[str]]]:
    """The handoffs made in the conversation, as (reason code, the sections their results gave)."""
    found = []
    for message in history:
        if message.get("role") != "tool" or message.get("name") != "request_handoff":
            continue
        try:
            result = json.loads(message.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and result.get("ok") and result.get("reason_code") in HANDOFF_CASES:
            found.append(
                (result["reason_code"], [c for c in result.get("policy_citations") or [] if isinstance(c, str)])
            )
    return found


def _tool_facts(
    history: Sequence[dict],
) -> tuple[dict[str, None], set[str], dict[str, tuple[str, frozenset[str]]]]:
    """Receipts shown as paid (in order), receipts paid in this conversation, and each order's latest read: its status
    and the words of its products. A later read of an order replaces the earlier one; a read without units keeps the
    earlier words."""
    shown: dict[str, None] = {}
    paid_here: set[str] = set()
    latest: dict[str, tuple[str, frozenset[str]]] = {}
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
            order_id, status = order.get("order_id"), order.get("status")
            if isinstance(order_id, str) and isinstance(status, str):
                words = latest.get(order_id, ("", frozenset()))[1]
                if isinstance(order.get("units"), list):
                    products = " ".join(str(u.get("product") or "") for u in order["units"] if isinstance(u, dict))
                    words = frozenset(_WORD.findall(products.lower()))
                latest[order_id] = (status, words)
            for request in order.get("requests") or []:
                if isinstance(request, dict) and request.get("receipt_number"):
                    shown[request["receipt_number"]] = None
        request = result.get("request")
        if isinstance(request, dict) and isinstance(request.get("receipt"), dict):
            number = request["receipt"].get("receipt_number")
            if number:
                shown[number] = None
    return shown, paid_here, latest


def _named_orders(answer: str, latest: dict[str, tuple[str, frozenset[str]]]) -> set[str]:
    """The orders the answer names: by their ID, or by a word of their products that no other order in view has."""
    text_ = answer.lower()
    words = set(_WORD.findall(text_))
    named = set()
    for order_id, (_, own) in latest.items():
        others = set().union(*(w for other, (_, w) in latest.items() if other != order_id))
        if re.search(rf"(?<![a-z0-9-]){re.escape(order_id.lower())}(?![a-z0-9-])", text_) or (own - others) & words:
            named.add(order_id)
    return named


def fact_line(history: Sequence[dict], answer: str, policy: Policy) -> str:
    """The line to say after the agent's answer, or "" when none is due. history: the conversation's messages before
    the answer, as the graph keeps them."""
    said_before = " ".join(m.get("text") or "" for m in history if m.get("role") == "agent")
    shown, paid_here, latest = _tool_facts(history)
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
            for order_id, (status, _) in latest.items()
            if status in STATUS_WORDS and re.search(rf"\b{status}\b", answer, re.IGNORECASE)
        ]
        about = _named_orders(answer, latest)
        if about:
            named = [(order_id, status) for order_id, status in named if order_id in about]
        if named:
            orders = ", ".join(f"order {order_id} is {status}" for order_id, status in named)
            sentences.append(
                f"Only orders recorded as delivered can be refunded through this process, and {orders} ({eligible})."
            )
    for code, citations in _handoffs(history):
        missing = [c for c in citations if c not in answer and c not in said_before]
        if missing:
            sentences.append(f"{HANDOFF_CASES[code]} ({'), ('.join(missing)}).")
    return " ".join(sentences)
