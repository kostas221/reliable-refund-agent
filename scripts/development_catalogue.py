"""Print the catalogue of development situations for an author package: one row per development scenario, with the
shape of its records and the outcome a correct conversation reaches, so that an author can check a candidate against
what is already used. Reads scenarios/development only; names no file and no link, since the author sees nothing else.

    uv run python scripts/development_catalogue.py > catalogue.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run as a script, from any folder

from refund_agent.scenarios import load_split  # noqa: E402


def money(minor: int) -> str:
    return f"R$ {minor // 100},{minor % 100:02d}"


def records(scenario) -> str:
    """The shape of the starting data: the customer's orders and units, returns, earlier refunds and proposals, payment
    records and seller messages; other customers' orders are counted apart."""
    mine = [o for o in scenario.fixture.orders if o.customer == scenario.customer.id]
    others = len(scenario.fixture.orders) - len(mine)
    parts = []
    for order in mine:
        units = order.units
        products = Counter(u.product for u in units)
        returned = sum(1 for u in units if u.received_back_at is not None)
        shape = f"{len(units)} unit{'s' if len(units) != 1 else ''}"
        if len(products) < len(units):
            shape += f" ({len(products)} product{'s' if len(products) != 1 else ''})"
        details = [shape, f"{returned} returned"]
        if order.status != "delivered":
            details.append(order.status)
        elif order.delivered_at is None:
            details.append("no delivery time")
        if len(order.payments) != 1:
            details.append(f"{len(order.payments)} payment records")
        if any(u.paid_minor < u.price_minor for u in units):
            details.append("discount")
        if order.seller_message_untrusted:
            details.append("seller message")
        parts.append("order: " + ", ".join(details))
    refunded = sum(len(r.units) for r in scenario.fixture.past_refunds)
    if refunded:
        parts.append(f"{refunded} unit{'s' if refunded != 1 else ''} refunded before")
    for proposal in scenario.fixture.past_proposals:
        parts.append(f"earlier proposal {proposal.status}")
    if others:
        parts.append(f"{others} order{'s' if others != 1 else ''} of another customer")
    return "; ".join(parts)


def outcome(scenario) -> str:
    expected = scenario.expected
    if expected.refunded_units:
        n = len(expected.refunded_units)
        return f"refund of {n} unit{'s' if n != 1 else ''}"
    return "no refund (" + " or ".join(expected.last_proposal_status) + ")"


def main() -> None:
    print("| ID | Group | Situation | Records | Correct end | Handoff | Required citations | Communication |")
    print("|---|---|---|---|---|---|---|---|")
    for s in sorted(load_split("development"), key=lambda s: int(s.id[1:])):
        cites = ", ".join(c.rsplit("/", 1)[-1] for c in s.expected.cites) or "-"
        print(
            f"| {s.id} | {s.category} | {s.title} | {records(s)} | {outcome(s)} | {s.expected.handoff} | {cites} | "
            f"{', '.join(s.expected.communication) or '-'} |"
        )


if __name__ == "__main__":
    main()
