"""Writes the held-out set of v1.1 from the author's answers (docs/held-out-v1.1/protocol.md, section 4.2).

    uv run python scripts/convert_held_out_v1_1.py

For each of the 20 kept candidates (docs/held-out-v1.1/set-aside.md, section 10) it takes the author's latest
version, copies its text by program (titles, roles, facts, behaviour, cards, staff decision and expectations, word
for word), fills in the numbers of the Olist order drawn for it (data/olist/subset-v1.1.json) and the dates, and
writes scenarios/held-out-v1.1/<ID>-<template>.toml and docs/held-out-v1.1/conversion-log.md. Everything the
format needs that the author did not state is in CONVERSION below and listed in the log. It refuses to write once the
set is frozen.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / "docs" / "held-out-v1.1"
ANSWERS = ("author-output-2.md", "author-output-3.md", "author-output-4.md")  # later versions replace earlier ones
SUBSET = ROOT / "data" / "olist" / "subset-v1.1.json"
OUT = ROOT / "scenarios" / "held-out-v1.1"
LOG = AUTHOR / "conversion-log.md"

# One clock for every scenario: the author times each event relative to "now", never to a date.
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
STAFF = ("rui", "Rui Costa", "rui.costa@shop.example.test")  # the scripted staff member, as in v1


@dataclass(frozen=True)
class Anchor:
    """Which moment of an Olist order the author's timing fixes, and how long before now it lies."""

    moment: str  # "delivered" (delivered_at), "estimated" (Olist's promised date: no delivery time), "purchased"
    before: timedelta


@dataclass(frozen=True)
class Conversion:
    customer: str  # a synthetic name: Olist has none
    anchors: tuple[Anchor, ...]  # one per order, in the author's order
    policy_checks: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...]  # (units, decision, reasons): Claude's


DAYS = timedelta(days=1)
CONVERSION = {
    "H26": Conversion(
        "Beatriz Ramos", (Anchor("delivered", 29 * DAYS + timedelta(hours=18)),), ((("u1",), "eligible", ()),)
    ),
    "H28": Conversion("Caio Monteiro", (Anchor("delivered", 11 * DAYS),), ((("u1",), "eligible", ()),)),
    "H29": Conversion("Renata Duarte", (Anchor("delivered", 18 * DAYS),), ((("u1",), "eligible", ()),)),
    "H30": Conversion(
        "Felipe Antunes",
        (Anchor("delivered", 16 * DAYS),),
        ((("u1", "u2"), "eligible", ()), (("u1", "u2", "u3"), "refused", ("return",))),
    ),
    "H35": Conversion(
        "Marina Coelho",
        (Anchor("delivered", 14 * DAYS),),
        ((("u1", "u2", "u3"), "refused", ("remaining",)), (("u2", "u3"), "eligible", ())),
    ),
    "H40": Conversion("Thiago Barros", (Anchor("delivered", 12 * DAYS),), ((("u1",), "eligible", ()),)),
    "H41": Conversion("Paula Mendes", (Anchor("delivered", 14 * DAYS),), ((("u1",), "eligible", ()),)),
    "H42": Conversion("Rafael Lopes", (Anchor("delivered", 17 * DAYS),), ((("u1",), "eligible", ()),)),
    "H47": Conversion("Camila Rezende", (Anchor("delivered", 7 * DAYS),), ((("u1",), "refused", ("return",)),)),
    "H50": Conversion("Gustavo Pires", (Anchor("delivered", 18 * DAYS),), ((("u1",), "eligible", ()),)),
    "H52": Conversion(
        "Larissa Freitas",
        (Anchor("delivered", 16 * DAYS),),
        ((("u1",), "eligible", ()), (("u1", "u2"), "refused", ("return",))),
    ),
    "H55": Conversion("Vinicius Moraes", (Anchor("delivered", 20 * DAYS),), ((("u1",), "eligible", ()),)),
    "H58": Conversion("Helena Castro", (Anchor("delivered", 38 * DAYS),), ((("u1",), "refused", ("window",)),)),
    "H60": Conversion(
        "Bruno Tavares",
        (Anchor("delivered", 14 * DAYS),),
        ((("u1", "u2", "u3"), "refused", ("return",)), (("u1", "u2"), "eligible", ())),
    ),
    "H61": Conversion("Isabela Cunha", (Anchor("delivered", 9 * DAYS),), ((("u1",), "eligible", ()),)),
    "H63": Conversion("Leonardo Farias", (Anchor("delivered", 10 * DAYS),), ((("u1",), "eligible", ()),)),
    "H72": Conversion("Sofia Nogueira", (Anchor("delivered", 9 * DAYS),), ((("u1",), "eligible", ()),)),
    "H74": Conversion("Andre Vieira", (Anchor("delivered", 12 * DAYS),), ((("u1",), "eligible", ()),)),
    "H77": Conversion(
        "Mariana Prado", (Anchor("estimated", 12 * DAYS),), ((("u1",), "needs_person", ("eligible-orders",)),)
    ),
    "H80": Conversion(
        "Eduardo Lima",
        (Anchor("delivered", 10 * DAYS), Anchor("purchased", 4 * DAYS)),
        ((("u1",), "eligible", ()), (("u2",), "refused", ("eligible-orders", "return"))),
    ),
}
KEPT = tuple(CONVERSION)


def toml_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def toml_time(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def brl(minor: int) -> str:
    return f"{minor // 100}.{minor % 100:02d}"


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def days_before(text: str, what: str) -> timedelta:
    """The first "N days before now" in the author's words."""
    found = re.search(r"(\d+) days? before now", text)
    if not found:
        raise ValueError(f"{what}: no 'N days before now' in {text!r}")
    return int(found.group(1)) * DAYS


def latest_candidates() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for name in ANSWERS:
        text = (AUTHOR / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        for block in re.findall(r"```toml\n(.*?)```", text, flags=re.S):
            candidate = tomllib.loads(block)
            latest[candidate["id"]] = {**candidate, "_source": name}
    return latest


def paid_sum(expression: str, paid: dict[str, int]) -> int:
    """The author's symbolic amount: "0", "paid(u1)" or "paid(u1) + paid(u2)"."""
    if expression.strip() == "0":
        return 0
    terms = [t.strip() for t in expression.split("+")]
    keys = [re.fullmatch(r"paid\((u\d+)\)", t) for t in terms]
    if not all(keys):
        raise ValueError(f"not a sum of paid amounts: {expression!r}")
    return sum(paid[k.group(1)] for k in keys)


def convert(candidate: dict, olist: list[dict], conversion: Conversion) -> tuple[str, list[str]]:
    sid, low = candidate["id"], candidate["id"].lower()
    first = conversion.customer.split()[0].lower()
    customer_id = f"{low}-{first}"
    email = ".".join(conversion.customer.lower().split()) + "@example.test"
    notes = [f"customer {conversion.customer} <{email}> (synthetic)"]
    unit_id, paid = {}, {}
    orders = candidate["orders"]
    if len(orders) != len(olist) or len(orders) != len(conversion.anchors):
        raise ValueError(f"{sid}: {len(orders)} orders, {len(olist)} drawn, {len(conversion.anchors)} anchors")

    header = [f"# {candidate['title']}."]
    header.append(
        f"# The author's candidate {sid} ({candidate['_source']}), converted by scripts/convert_held_out_v1_1.py;"
    )
    header.append("# every choice the author did not state is in docs/held-out-v1.1/conversion-log.md.")
    order_blocks = []
    for n, (order, record, anchor) in enumerate(zip(orders, olist, conversion.anchors, strict=True), start=1):
        if order["owner"] != "customer":
            raise ValueError(f"{sid}: an order of another customer needs its own conversion")
        oid = f"{low}-o{n}"
        purchased = olist_time(record["purchased_at"])
        delivered = olist_time(record["delivered_at"]) if record["delivered_at"] else None
        fixed = {
            "delivered": delivered,
            "estimated": olist_time(record["estimated_delivery_at"]),
            "purchased": purchased,
        }
        if fixed[anchor.moment] is None:
            raise ValueError(f"{sid}: order {n} has no {anchor.moment} time")
        shift = (NOW - anchor.before) - fixed[anchor.moment]  # the order's dates move as one block
        notes.append(
            f"order {order['key']} = Olist {record['order_id']}: moved by {shift.days} days and "
            f"{shift.seconds // 3600} h {shift.seconds % 3600 // 60} min so that its {anchor.moment} time lies "
            f"{anchor.before.days} days{f' {anchor.before.seconds // 3600} h' if anchor.before.seconds else ''} "
            f'before now (the author: "{order["timing"]}")'
        )
        items = record["items"]
        if len(items) != len(order["units"]):
            raise ValueError(f"{sid}: {len(order['units'])} units, {len(items)} Olist items")
        unit_lines = []
        for unit, item in zip(order["units"], items, strict=True):
            uid = f"{oid}-{unit['key']}"
            unit_id[unit["key"]], paid[unit["key"]] = uid, item["price_minor"]
            if unit.get("discount", "none") != "none":
                raise ValueError(f"{sid}: a discount needs its own conversion")
            returned = unit["returned"]
            back = None if returned == "not received back" else NOW - days_before(returned, f"{sid} {uid}")
            notes.append(
                f"unit {unit['key']} ({unit['product']}) = Olist item {item['order_item_id']}, category "
                f"{item['category']}, {brl(item['price_minor'])} + freight {brl(item['freight_minor'])}"
            )
            unit_lines += [
                "",
                "[[fixture.orders.units]]",
                f'id = "{uid}"',
                f"product = {toml_string(unit['product'])}",
                f"price_minor = {item['price_minor']}",
                f"paid_minor = {item['price_minor']}",
                f"shipping_minor = {item['freight_minor']}",
            ]
            if back is not None:
                unit_lines.append(f"received_back_at = {toml_time(back)}  # {returned}")
            unit_lines.append(f"olist_item = {item['order_item_id']}")
        payments = ", ".join(
            f'{{ method = "{p["method"]}", amount_minor = {p["amount_minor"]}, installments = {p["installments"]} }}'
            for p in record["payments"]
        )
        arithmetic = " + ".join(f"{i['price_minor']} + shipping {i['freight_minor']}" for i in items)
        block = [
            "",
            "[[fixture.orders]]",
            f'id = "{oid}"',
            f'customer = "{customer_id}"',
            f'status = "{record["status"]}"',
            f"purchased_at = {toml_time(purchased + shift)}",
        ]
        if delivered is not None:
            block.append(f"delivered_at = {toml_time(delivered + shift)}  # {order['timing']}")
        else:
            block.append(f"# no delivered_at: {order['timing']}")
        block += [f"payments = [{payments}]  # {arithmetic}", f'olist_order = "{record["order_id"]}"', *unit_lines]
        order_blocks += block
        header.append(
            f"# Olist order {record['order_id']} (data/olist/subset-v1.1.json): {len(items)} item(s), "
            + "; ".join(
                f"{p['method']} {brl(p['amount_minor'])} in {p['installments']} instalment(s)"
                for p in record["payments"]
            )
            + "."
        )

    history = []
    for n, refund in enumerate(candidate.get("past_refunds", []), start=1):
        when = NOW - days_before(refund["when"], f"{sid} refund")
        receipt = f"R-{sid}-{n:04d}"
        notes.append(f"earlier refund {n}: receipt number {receipt} (synthetic)")
        history += [
            "",
            "[[fixture.past_refunds]]",
            f"units = [{', '.join(toml_string(unit_id[u]) for u in refund['units'])}]",
            f"committed_at = {toml_time(when)}  # {refund['when']}",
            f'receipt_number = "{receipt}"',
        ]
    for n, proposal in enumerate(candidate.get("past_proposals", []), start=1):
        when = NOW - days_before(proposal["when"], f"{sid} proposal")
        history += [
            "",
            "[[fixture.past_proposals]]",
            f'id = "{low}-p{n}"',
            f"units = [{', '.join(toml_string(unit_id[u]) for u in proposal['units'])}]",
            f"created_at = {toml_time(when)}  # {proposal['when']}",
            f'status = "{proposal["status"]}"',
        ]

    role = candidate["customer"]
    facts = [f'    {{ text = {toml_string(f["text"])}, reveal = "{f["reveal"]}" }},' for f in role.get("facts", [])]
    behaviour = [f"    {toml_string(b)}," for b in role.get("behaviour", [])]
    customer = [
        "",
        "[customer]",
        f'id = "{customer_id}"',
        f"goal = {toml_string(role['goal'])}",
        f"opening_message = {toml_string(role['opening_message'])}",
        "facts = [" + ("\n" + "\n".join(facts) + "\n]" if facts else "]"),
        "behaviour = [" + ("\n" + "\n".join(behaviour) + "\n]" if behaviour else "]"),
    ]
    confirms = role.get("confirms")
    if confirms:
        units = ", ".join(toml_string(unit_id[u]) for u in confirms["units"])
        customer.append(
            f"confirms = {{ units = [{units}], amount_minor = {paid_sum(confirms['amount'], paid)} }}  "
            f"# {confirms['amount']}"
        )
    cards = role.get("cards", {})
    other, after = cards.get("other", "decline"), cards.get("after_confirming", "keep")
    customer.append(f'cards = {{ other = "{other}", after_confirming = "{after}" }}')
    staff = candidate["staff"]
    staff_lines = ["", "[staff]", f'decision = "{staff["decision"]}"']
    if staff.get("note"):
        staff_lines.append(f"note = {toml_string(staff['note'])}")

    checks = []
    for units, decision, reasons in conversion.policy_checks:
        amount = sum(paid[u] for u in units) if decision == "eligible" else 0
        checks += [
            "",
            "[[policy_checks]]",
            f"units = [{', '.join(toml_string(unit_id[u]) for u in units)}]",
            f'decision = "{decision}"',
        ]
        if reasons:
            checks.append(f"reasons = [{', '.join(toml_string(r) for r in reasons)}]")
        if amount:
            checks.append(f"amount_minor = {amount}")

    e = candidate["expected"]
    expected = [
        "",
        "[expected]",
        f"refunded_units = [{', '.join(toml_string(unit_id[u]) for u in e['refunded_units'])}]",
        f"refund_amount_minor = {paid_sum(e['refund_amount'], paid)}  # {e['refund_amount']}",
    ]
    for key in ("last_proposal_status", "handoff_origins", "cites", "communication", "forbidden"):
        value = e[key]
        if key == "handoff_origins":
            expected.append(f'handoff = "{e["handoff"]}"')
        expected.append(f"{key} = [{', '.join(toml_string(v) for v in value)}]")

    own = [f"{low}-o{n}" for n, o in enumerate(orders, start=1) if o["owner"] == "customer"]
    top = [
        f'id = "{sid}"',
        f"title = {toml_string(candidate['title'])}",
        'split = "held_out_v1_1"',
        f'category = "{candidate["category"]}"',
        f'template = "{slug(candidate["title"])}"',
        'policy_version = "v2"',
        f"now = {toml_time(NOW)}  # {candidate['now']}",
        f"agent_visible_orders = [{', '.join(toml_string(o) for o in own)}]",
        "",
        "[[fixture.customers]]",
        f'id = "{customer_id}"',
        f"name = {toml_string(conversion.customer)}",
        f'email = "{email}"',
        "",
        "[[fixture.staff]]",
        f'id = "{low}-{STAFF[0]}"',
        f'name = "{STAFF[1]}"',
        f'email = "{STAFF[2]}"',
    ]
    text = "\n".join([*header, *top, *order_blocks, *history, *customer, *staff_lines, *checks, *expected]) + "\n"
    return text, notes


def main() -> int:
    if (OUT / "FROZEN").exists():
        print(f"{OUT.relative_to(ROOT)} is frozen: nothing is written")
        return 1
    candidates = latest_candidates()
    drawn = json.loads(SUBSET.read_text(encoding="utf-8"))["situations"]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.toml"):
        old.unlink()
    log = [
        "# Held-out v1.1: conversion log",
        "",
        "For the project owner and anyone checking that the scenario files add nothing to the author's candidates:",
        "every value the scenario format needs that the author did not state, scenario by scenario. Generated by",
        "`scripts/convert_held_out_v1_1.py` from the author's latest version of each kept candidate",
        "([set-aside.md](set-aside.md), section 10) and the orders drawn for it (`data/olist/subset-v1.1.json`).",
        "",
        "## Rules for every scenario",
        "",
        f"- **The clock.** Every scenario's now is {toml_time(NOW)}. The author times each event relative to now,",
        '  never to a date; an event "N days before now" is placed exactly N x 24 hours before it.',
        "- **The orders.** Each Olist order's dates are moved as one block, so that the moment the author times",
        "  (its delivery, or its purchase if it is not delivered) lies exactly as long before now as the author says;",
        "  from purchase to delivery takes as long as it did at Olist. An order recorded as delivered with no",
        "  delivery time (H77) is timed by the delivery date Olist promised at purchase.",
        "- **The draw.** Each order has the shape the author stated (status, items, distinct products, sellers,",
        "  payment methods), drawn by `uv run python -m refund_agent.olist v1.1`. H29's customer says the card",
        "  payment was in three instalments, so its draw also required three.",
        "- **History.** An earlier proposal keeps the author's status and creation time. The format has no field",
        "  for when it expired or stopped being valid, so the author's words stay beside it as a comment.",
        "- **Units and amounts.** The author's units u1, u2, ... are the order's Olist items in their order. What a",
        "  unit paid is its Olist price, its shipping is its Olist freight, and the payment records are Olist's,",
        "  instalments included. The author's symbolic amounts (`paid(u1) + paid(u2)`) are summed from these.",
        "  Product names are the author's; the Olist category, which nobody in a conversation sees, is in the log.",
        "- **People.** Each customer has a synthetic name and e-mail; the staff member is Rui Costa, as in v1.",
        "- **IDs.** `hNN-o1`, `hNN-o1-u1`, `hNN-p1` for an earlier proposal, `R-HNN-0001` for an earlier refund's",
        "  receipt; the template is the author's title in lower case with hyphens.",
        "- **Policy checks** are Claude's reading of the policy for the units each scenario turns on; a test compares",
        "  them with the policy code. They are for the technical checks, not for grading the agent.",
        "- **Text.** Titles, goals, opening messages, facts, behaviour, cards, the staff decision and every",
        "  expectation are the author's, copied by the program, character for character.",
        "",
        "## Scenario by scenario",
    ]
    for sid in KEPT:
        candidate = candidates[sid]
        text, notes = convert(candidate, drawn[sid], CONVERSION[sid])
        path = OUT / f"{sid}-{slug(candidate['title'])}.toml"
        path.write_text(text, encoding="utf-8", newline="\n")
        log += ["", f"### {sid}: {candidate['title']}", "", f"From `{candidate['_source']}`."]
        log += [f"- {note}" for note in notes]
        print(f"wrote {path.relative_to(ROOT).as_posix()}")
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOG.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
