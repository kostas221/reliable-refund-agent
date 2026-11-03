"""Writes the comparison set of v1.3 from the author's selected candidates (docs/held-out-v1.3/protocol.md, section 4).

    uv run python scripts/convert_held_out_v1_3.py

For each of the 39 selected candidates (docs/held-out-v1.3/selected-39-manifest.json) it reads the author's block
from selected-39-author-specifications.md, refuses it unless its SHA-256 is the manifest's, copies its text by
program (title, role, facts, behaviour, cards, staff decision, seller messages, expectations, citations, obligations
and quality citations, word for word), fills in the numbers of the Olist orders drawn for it
(data/olist/subset-v1.3.json) and the dates, and writes scenarios/held-out-v1.3/<ID>-<template>.toml and
docs/held-out-v1.3/conversion-log.md. Everything the format needs that the author did not state is in CONVERSION and
the rules below, and is listed in the log. It refuses to write once the set is frozen.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "held-out-v1.3"
SPECIFICATIONS = DOCS / "selected-39-author-specifications.md"
MANIFEST = DOCS / "selected-39-manifest.json"
SUBSET = ROOT / "data" / "olist" / "subset-v1.3.json"
OUT = ROOT / "scenarios" / "held-out-v1.3"
LOG = DOCS / "conversion-log.md"
SPLIT = "held_out_v1_3"

# One clock for every scenario, as in v1.1 and v1.2: the author times each event relative to "now", never to a date.
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
STAFF = ("rui", "Rui Costa", "rui.costa@shop.example.test")  # the scripted staff member, as in every set
DAYS = timedelta(days=1)
ELIGIBLE, REFUSED, PERSON = "eligible", "refused", "needs_person"


@dataclass(frozen=True)
class Check:
    """Claude's reading of the policy for some of the author's units, compared with the policy code by a test."""

    units: tuple[str, ...]
    decision: str
    reasons: tuple[str, ...] = ()
    earlier_on_time: bool = False  # an earlier proposal for these units was created in time and then stopped


@dataclass(frozen=True)
class Conversion:
    customer: str  # a synthetic name: Olist has none
    checks: tuple[Check, ...]
    other: str = ""  # the synthetic name of the other customer, when an order is another customer's


def ok(*units: str) -> Check:
    return Check(units, ELIGIBLE)


def no(units: tuple[str, ...] | str, *reasons: str) -> Check:
    return Check((units,) if isinstance(units, str) else units, REFUSED, reasons)


CONVERSION = {
    # eligible
    "H401": Conversion("Renata Figueiredo", (ok("u2", "u3"), ok("u2"), ok("u1"), no("u4", "return"))),
    "H402": Conversion("Caio Moreira", (ok("u1"),)),
    "H403": Conversion("Larissa Antunes", (no("u1", "window"), ok("u2"), no("u3", "eligible-orders", "return"))),
    "H404": Conversion("Thiago Barreto", (ok("u1"), no("u2", "return"), no(("u1", "u2"), "return"))),
    "H405": Conversion("Camila Vasconcelos", (ok("u1"), ok("u1", "u2"), no("u3", "return"))),
    "H406": Conversion("Eduardo Lins", (no(("u1", "u2", "u3"), "remaining"), ok("u2", "u3"))),
    "H407": Conversion(
        "Marina Couto", (ok("u1"), no("u2", "return"), no("u3", "eligible-orders", "return")), other="Paulo Siqueira"
    ),
    "H409": Conversion("Beatriz Falcao", (ok("u1"), no("u2", "return"))),
    "H410": Conversion("Rafael Toledo", (ok("u1"), ok("u2"))),
    "H411": Conversion("Juliana Prado", (ok("u1"), no("u2", "return"), no("u3", "eligible-orders", "return"))),
    "H412": Conversion("Gustavo Neves", (ok("u2"), no("u1", "remaining"))),
    "H414": Conversion("Fernanda Bastos", (ok("u1", "u2"),)),
    "H415": Conversion("Lucas Furtado", (ok("u1", "u2"), no("u3", "return"))),
    "H416": Conversion("Aline Godoy", (no(("u1", "u2", "u3"), "return"), ok("u1", "u2"))),
    # ineligible
    "H420": Conversion("Marcelo Dantas", (no("u1", "window"),)),
    "H421": Conversion("Patricia Leal", (no("u1", "return"),)),
    "H422": Conversion("Sergio Batalha", (no("u1", "remaining"), no("u2", "window"), no("u3", "return"))),
    "H424": Conversion("Vanessa Quaresma", (no("u1", "window"), no("u2", "eligible-orders", "return"))),
    "H425": Conversion("Daniel Assuncao", (no("u1", "remaining"),)),
    "H426": Conversion("Carolina Mesquita", (no(("u1", "u2"), "remaining"), ok("u2"))),
    "H427": Conversion("Leandro Paiva", (no("u1", "window"),)),
    "H428": Conversion("Bruna Sarmento", (ok("u1"), no("u2", "return"))),
    # attack
    "H432": Conversion(
        "Felipe Arruda",
        (ok("u2"), no("u1", "return"), no("u3", "eligible-orders", "return")),
        other="Mauricio Lago",
    ),
    "H433": Conversion("Isabela Cardoso", (ok("u1"),)),
    "H435": Conversion("Andre Galvao", (ok("u1"),)),
    "H436": Conversion("Debora Pacheco", (no(("u1", "u2"), "remaining"), ok("u2"))),
    "H438": Conversion("Viviane Torres", (ok("u1"),), other="Luana Torres"),
    "H440": Conversion("Regina Fontoura", (ok("u1"),)),
    "H441": Conversion("Wagner Castilho", (ok("u1"),)),
    "H442": Conversion("Elaine Ventura", (ok("u1"),)),
    # clarification_handoff: six required handoffs, then three clarifications without one
    "H461": Conversion(
        "Roberto Saldanha",
        (Check(("u2",), PERSON, ("window",), earlier_on_time=True), no("u1", "window", "remaining")),
    ),
    "H462": Conversion("Monica Brito", (ok("u1"), no("u2", "return"))),
    "H464": Conversion("Jessica Valadares", (no("u1", "window"), no("u2", "return"), no("u3", "return"))),
    "H465": Conversion("Fabiana Cunha", (ok("u1"), ok("u1", "u2"))),
    "H466": Conversion("Ricardo Bittencourt", (no("u1", "remaining"), no("u2", "return"))),
    "H468": Conversion("Adriana Seixas", (ok("u1"), no("u2", "eligible-orders", "return"))),
    "H469": Conversion("Carla Mattos", (ok("u2"), ok("u1"), ok("u3"))),
    "H471": Conversion("Sandra Novaes", (no("u1", "remaining"), ok("u2"), ok("u3"))),
    "H472": Conversion("Bruno Rangel", (ok("u1"), ok("u1", "u2"), no("u3", "return"))),
}
SELECTED = tuple(CONVERSION)  # in the manifest's order: the groups' order, each group in the author's order

# H421's order is paid by card and boleto, a pair no Olist order has (the draw found none in 99,441 orders). Its
# drawn order is a one-item order paid by card; the conversion splits that payment in two records of the same total.
SPLIT_PAYMENTS = {("H421", "o1"): ("credit_card", "boleto")}

TIMED = re.compile(r"(\d+) days?(?:(?: and)? (\d+) hours?)? before now")
LISTED = re.compile(r"listed (\d+)% above what was paid")
FENCE = re.compile(r"```toml\n(.*?)```", flags=re.S)


def toml_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def toml_list(values) -> str:
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


def toml_time(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def brl(minor: int) -> str:
    return f"{minor // 100}.{minor % 100:02d}"


def slug(title: str, limit: int = 60) -> str:
    """The title in lower case with hyphens, cut after the last whole word within `limit` characters: the authors'
    titles are long, and a full path on Windows must stay under 260 characters in any checkout."""
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-").split("-")
    kept = [words[0]]
    for word in words[1:]:
        if len("-".join([*kept, word])) > limit:
            break
        kept.append(word)
    return "-".join(kept)


def before_now(text: str, what: str) -> timedelta:
    """The first "N days [and H hours] before now" in the author's words."""
    found = TIMED.search(text)
    if not found:
        raise ValueError(f"{what}: no 'N days before now' in {text!r}")
    return int(found.group(1)) * DAYS + timedelta(hours=int(found.group(2) or 0))


def anchor(order: dict, sid: str) -> tuple[str, timedelta]:
    """Which moment of the order the author's timing fixes: its delivery, or, for an order on its way, its purchase."""
    timing = order["timing"]
    if order["status"] == "delivered":
        if not timing.startswith("delivered "):
            raise ValueError(f"{sid}: a delivered order timed by {timing!r}")
        return "delivered", before_now(timing, sid)
    if order["status"] == "shipped" and timing.startswith("bought "):
        return "purchased", before_now(timing, sid)
    raise ValueError(f"{sid}: no conversion for an order {order['status']!r} timed {timing!r}")


def listed_price(paid: int, discount: str, what: str) -> int:
    """The price the shop listed, from the author's "listed N% above what was paid", rounded half up to the centavo."""
    if discount == "none":
        return paid
    found = LISTED.fullmatch(discount)
    if not found:
        raise ValueError(f"{what}: no conversion for the discount {discount!r}")
    return (paid * (100 + int(found.group(1))) + 50) // 100


def paid_sum(expression: str, paid: dict[str, int]) -> int:
    """The author's symbolic amount: "0", "paid(u1)" or "paid(u1) + paid(u2)"."""
    if expression.strip() == "0":
        return 0
    terms = [t.strip() for t in expression.split("+")]
    keys = [re.fullmatch(r"paid\((u\d+)\)", t) for t in terms]
    if not all(keys):
        raise ValueError(f"not a sum of paid amounts: {expression!r}")
    return sum(paid[k.group(1)] for k in keys)


def split_payment(payment: dict, methods: tuple[str, str]) -> list[dict]:
    """One Olist payment as two records of the same total: the first method keeps the instalments and the larger
    half, the second pays the rest at once."""
    second = payment["amount_minor"] // 2
    return [
        {
            "method": methods[0],
            "amount_minor": payment["amount_minor"] - second,
            "installments": payment["installments"],
        },
        {"method": methods[1], "amount_minor": second, "installments": 1},
    ]


def selected_candidates() -> dict[str, dict]:
    """The selected blocks, in the manifest's order, each refused unless its SHA-256 is the manifest's."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wanted = {c["id"]: c for c in manifest["candidates"]}
    text = SPECIFICATIONS.read_bytes().decode("utf-8")
    blocks = {}
    for block in FENCE.findall(text):
        candidate = tomllib.loads(block)
        listed = wanted[candidate["id"]]
        if hashlib.sha256(block.encode("utf-8")).hexdigest() != listed["author_block_sha256"]:
            raise ValueError(f"{candidate['id']}: the block is not the one the manifest records")
        blocks[candidate["id"]] = {**candidate, "_source": f"{listed['source_path']}, line {listed['source_line']}"}
    if list(blocks) != list(wanted):
        raise ValueError("the specifications do not hold the manifest's candidates in its order")
    return blocks


def person(name: str) -> tuple[str, str]:
    """A synthetic person's first name in lower case and e-mail."""
    return name.split()[0].lower(), ".".join(name.lower().split()) + "@example.test"


def convert(candidate: dict, olist: list[dict], conversion: Conversion) -> tuple[str, list[str]]:
    sid, low = candidate["id"], candidate["id"].lower()
    first, email = person(conversion.customer)
    customer_id = f"{low}-{first}"
    people = [(customer_id, conversion.customer, email)]
    notes = [f"customer {conversion.customer} <{email}> (synthetic)"]
    other_id = ""
    if conversion.other:
        other_first, other_email = person(conversion.other)
        other_id = f"{low}-{other_first}"
        people.append((other_id, conversion.other, other_email))
        notes.append(f"the other customer {conversion.other} <{other_email}> (synthetic)")
    unit_id, paid = {}, {}
    orders = candidate["orders"]
    if len(orders) != len(olist):
        raise ValueError(f"{sid}: {len(orders)} orders, {len(olist)} drawn")
    if any(o["owner"] == "other" for o in orders) != bool(conversion.other):
        raise ValueError(f"{sid}: another customer's order needs the other customer's name, and only then")

    header = [f"# {candidate['title']}."]
    header.append(f"# The author's candidate {sid} ({candidate['_source']}), converted by")
    log = LOG.relative_to(ROOT).as_posix()
    header.append(f"# scripts/convert_held_out_v1_3.py; every choice the text did not state is in {log}.")
    order_blocks = []
    for n, (order, record) in enumerate(zip(orders, olist, strict=True), start=1):
        if order["key"] != f"o{n}":
            raise ValueError(f"{sid}: the orders are not o1, o2, ... in order")
        owner = {"customer": customer_id, "other": other_id}[order["owner"]]
        oid = f"{low}-o{n}"
        moment, before = anchor(order, sid)
        purchased = olist_time(record["purchased_at"])
        delivered = olist_time(record["delivered_at"]) if record["delivered_at"] else None
        fixed = {"delivered": delivered, "purchased": purchased}[moment]
        if fixed is None:
            raise ValueError(f"{sid}: order {n} has no {moment} time")
        shift = (NOW - before) - fixed  # the order's dates move as one block
        hours = f" {before.seconds // 3600} h" if before.seconds else ""
        whose = " (another customer's)" if order["owner"] == "other" else ""
        notes.append(
            f"order {order['key']}{whose} = Olist {record['order_id']}: moved by {shift.days} days and "
            f"{shift.seconds // 3600} h {shift.seconds % 3600 // 60} min so that its {moment} time lies "
            f'{before.days} days{hours} before now (the author: "{order["timing"]}")'
        )
        if order.get("tie"):
            notes.append(f'order {order["key"]} drawn as the author tied it: "{order["tie"]}"')
        items = record["items"]
        if len(items) != len(order["units"]):
            raise ValueError(f"{sid}: {len(order['units'])} units, {len(items)} Olist items")
        unit_lines = []
        for unit, item in zip(order["units"], items, strict=True):
            uid = f"{oid}-{unit['key']}"
            unit_id[unit["key"]], paid[unit["key"]] = uid, item["price_minor"]
            price = listed_price(item["price_minor"], unit.get("discount", "none"), f"{sid} {uid}")
            returned = unit["returned"]
            back = None if returned == "not received back" else NOW - before_now(returned, f"{sid} {uid}")
            note = (
                f"unit {unit['key']} ({unit['product']}) = Olist item {item['order_item_id']}, category "
                f"{item['category']}, paid {brl(item['price_minor'])} + freight {brl(item['freight_minor'])}"
            )
            if price != item["price_minor"]:
                note += f'; listed price {brl(price)} (the author: "{unit["discount"]}")'
            notes.append(note)
            unit_lines += [
                "",
                "[[fixture.orders.units]]",
                f'id = "{uid}"',
                f"product = {toml_string(unit['product'])}",
                f"price_minor = {price}" + (f"  # {unit['discount']}" if price != item["price_minor"] else ""),
                f"paid_minor = {item['price_minor']}",
                f"shipping_minor = {item['freight_minor']}",
            ]
            if back is not None:
                unit_lines.append(f"received_back_at = {toml_time(back)}  # {returned}")
            unit_lines.append(f"olist_item = {item['order_item_id']}")
        payments = record["payments"]
        split = SPLIT_PAYMENTS.get((sid, order["key"]))
        if split:
            if len(payments) != 1:
                raise ValueError(f"{sid}: only a single payment is split")
            payments = split_payment(payments[0], split)
            notes.append(
                f"order {order['key']}: paid by {' and '.join(split)} in the author's words, a pair no Olist order "
                f"has; the drawn order's one {record['payments'][0]['method']} payment of "
                f"{brl(record['payments'][0]['amount_minor'])} is split into "
                + " and ".join(f"{p['method']} {brl(p['amount_minor'])}" for p in payments)
                + " (synthetic, the total unchanged)"
            )
        listed = ", ".join(
            f'{{ method = "{p["method"]}", amount_minor = {p["amount_minor"]}, installments = {p["installments"]} }}'
            for p in payments
        )
        arithmetic = " + ".join(f"{i['price_minor']} + shipping {i['freight_minor']}" for i in items)
        block = [
            "",
            "[[fixture.orders]]",
            f'id = "{oid}"',
            f'customer = "{owner}"',
            f'status = "{record["status"]}"',
            f"purchased_at = {toml_time(purchased + shift)}",
        ]
        if delivered is not None:
            block.append(f"delivered_at = {toml_time(delivered + shift)}  # {order['timing']}")
        else:
            block.append(f"# no delivered_at: {order['timing']}")
        block.append(f"payments = [{listed}]  # {arithmetic}")
        if order.get("seller_message"):
            block.append(f"seller_message_untrusted = {toml_string(order['seller_message'])}")
        block += [f'olist_order = "{record["order_id"]}"', *unit_lines]
        order_blocks += block
        header.append(
            f"# Olist order {record['order_id']} ({SUBSET.relative_to(ROOT).as_posix()}): {len(items)} item(s), "
            + "; ".join(
                f"{p['method']} {brl(p['amount_minor'])} in {p['installments']} instalment(s)"
                for p in record["payments"]
            )
            + (" (split in two by the conversion)" if split else "")
            + "."
        )

    history = []
    for n, refund in enumerate(candidate.get("past_refunds", []), start=1):
        when = NOW - before_now(refund["when"], f"{sid} refund")
        receipt = f"R-{sid}-{n:04d}"
        notes.append(f"earlier refund {n}: receipt number {receipt} (synthetic)")
        history += [
            "",
            "[[fixture.past_refunds]]",
            f"units = {toml_list(unit_id[u] for u in refund['units'])}",
            f"committed_at = {toml_time(when)}  # {refund['when']}",
            f'receipt_number = "{receipt}"',
        ]
    for n, proposal in enumerate(candidate.get("past_proposals", []), start=1):
        when = NOW - before_now(proposal["when"], f"{sid} proposal")
        history += [
            "",
            "[[fixture.past_proposals]]",
            f'id = "{low}-p{n}"',
            f"units = {toml_list(unit_id[u] for u in proposal['units'])}",
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
        customer.append(
            f"confirms = {{ units = {toml_list(unit_id[u] for u in confirms['units'])}, "
            f"amount_minor = {paid_sum(confirms['amount'], paid)} }}  # {confirms['amount']}"
        )
    cards = role["cards"]
    customer.append(f'cards = {{ other = "{cards["other"]}", after_confirming = "{cards["after_confirming"]}" }}')
    staff = candidate["staff"]
    staff_lines = ["", "[staff]", f'decision = "{staff["decision"]}"']
    if staff.get("note"):
        staff_lines.append(f"note = {toml_string(staff['note'])}")

    checks = []
    for check in conversion.checks:
        amount = sum(paid[u] for u in check.units) if check.decision == ELIGIBLE else 0
        checks += [
            "",
            "[[policy_checks]]",
            f"units = {toml_list(unit_id[u] for u in check.units)}",
            f'decision = "{check.decision}"',
        ]
        if check.reasons:
            checks.append(f"reasons = {toml_list(check.reasons)}")
        if amount:
            checks.append(f"amount_minor = {amount}")
        if check.earlier_on_time:
            checks.append("earlier_request_on_time = true")

    e = candidate["expected"]
    expected = [
        "",
        "[expected]",
        f"refunded_units = {toml_list(unit_id[u] for u in e['refunded_units'])}",
        f"refund_amount_minor = {paid_sum(e['refund_amount'], paid)}  # {e['refund_amount']}",
        f"last_proposal_status = {toml_list(e['last_proposal_status'])}",
        f'handoff = "{e["handoff"]}"',
        f"handoff_origins = {toml_list(e['handoff_origins'])}",
        f"cites = {toml_list(e['cites'])}",
        f"quality_cites = {toml_list(e.get('quality_cites', []))}",
        f"communication = {toml_list(e['communication'])}",
        f"forbidden = {toml_list(e['forbidden'])}",
    ]
    obligations = e.get("obligations", {})
    if obligations:
        expected += ["", "[expected.obligations]"]
        expected += [f"{toml_string(section)} = {toml_string(text)}" for section, text in obligations.items()]

    own = [f"{low}-o{n}" for n, o in enumerate(orders, start=1) if o["owner"] == "customer"]
    top = [
        f'id = "{sid}"',
        f"title = {toml_string(candidate['title'])}",
        f'split = "{SPLIT}"',
        f'category = "{candidate["category"]}"',
        f'template = "{slug(candidate["title"])}"',
        'policy_version = "v2"',
        f"now = {toml_time(NOW)}",
        f"agent_visible_orders = {toml_list(own)}",
    ]
    for pid, name, mail in people:
        top += ["", "[[fixture.customers]]", f'id = "{pid}"', f"name = {toml_string(name)}", f'email = "{mail}"']
    top += ["", "[[fixture.staff]]", f'id = "{low}-{STAFF[0]}"', f'name = "{STAFF[1]}"', f'email = "{STAFF[2]}"']
    text = "\n".join([*header, *top, *order_blocks, *history, *customer, *staff_lines, *checks, *expected]) + "\n"
    return text, notes


INTRO = [
    "# Comparison set of v1.3: conversion log",
    "",
    "For the project owner and anyone checking that the scenario files add nothing to the author's candidates: every",
    "value the scenario format needs that the author did not state, scenario by scenario. Generated by",
    "`scripts/convert_held_out_v1_3.py` from the 39 selected candidates",
    "([selected-39-author-specifications.md](selected-39-author-specifications.md), each block checked against the",
    "SHA-256 in [selected-39-manifest.json](selected-39-manifest.json)) and the orders drawn for them",
    "(`data/olist/subset-v1.3.json`, `uv run python -m refund_agent.olist v1.3`).",
]
RULES = [
    "## Rules for every scenario",
    "",
    f"- **The clock.** Every scenario's now is {toml_time(NOW)}, as in v1.1 and v1.2. The author times each event",
    '  relative to now, never to a date; an event "N days [and H hours] before now" is placed exactly that long',
    "  before it. The candidates state no `now` of their own.",
    "- **The orders.** Each Olist order's dates move as one block, so that the moment the author times (its delivery,",
    "  or its purchase for an order still on its way) lies exactly as long before now as the author says; from",
    "  purchase to delivery takes as long as it did at Olist. The format has no field for when an order was shipped,",
    "  so the author's words for it stay beside the order as a comment.",
    "- **The draw.** Each order has the shape the author stated (status, items, distinct products, sellers, payment",
    "  methods), drawn by the lot, never an order of an earlier held-out or stress set. An order the author tied to",
    '  another ("same product as o1, other customer"; "same category as o1, another product") is drawn so; the',
    "  order a tie points to is the first by the lot that has such a partner. Tied by category, the products differ",
    "  from every other order of the scenario.",
    "- **One payment split.** No Olist order is paid by card and boleto together, the pair H421's author wrote. H421's",
    "  order is a real one-item order paid by card; its one payment is split into a card record and a boleto record",
    "  of the same total, the card keeping its instalments and the larger half. This is the set's only synthetic",
    "  payment record.",
    '- **Another customer\'s order.** An order the author marked `owner = "other"` (H407, H432, H438) belongs to a',
    "  second synthetic customer and is not among the orders the agent may see.",
    "- **History.** An earlier refund or proposal keeps the author's units, status and time; a refund's receipt",
    "  number is synthetic. The format has no field for when an earlier proposal expired or stopped being valid.",
    "- **Units and amounts.** The author numbers units across the orders (u1, u2, ... in the order of orders); they",
    "  are each order's Olist items in their order. What a unit paid is its Olist price, its shipping is its Olist",
    "  freight, and the payment records are Olist's, instalments included (except H421, above). The author's",
    '  symbolic amounts (`paid(u1) + paid(u2)`) are summed from these. Where the author wrote "listed N% above what',
    '  was paid", the listed price is the paid price times (100 + N) / 100, rounded half up to the centavo; Olist',
    "  has no discounts, so this price is synthetic and named in the scenario. Product names are the author's,",
    "  spelling included; the Olist category, which nobody in a conversation sees, is in the log.",
    "- **People.** Each customer, and each other customer, has a synthetic name and e-mail; the staff member is",
    "  Rui Costa, as in every set.",
    "- **IDs.** `hNNN-o1`, `hNNN-o1-u1`, `hNNN-p1` for an earlier proposal, `R-HNNN-0001` for an earlier refund's",
    "  receipt; a unit keeps the author's number, so the second order's first unit may be `hNNN-o2-u2`. The",
    "  template, which names the file, is the author's title in lower case with hyphens, cut after the last whole",
    "  word within 60 characters, so that a full path stays under Windows' 260 characters in any checkout.",
    "- **Policy checks** are Claude's reading of the policy for the units each scenario turns on; a test compares",
    "  them with the policy code. They are for the technical checks, not for grading the agent.",
    "- **Not kept from the author's block:** `novel`, `nearest`, `difference`, `rationale` and the orders' `shape`,",
    "  which the scenario format has no field for; they stay in the specifications and the manifest.",
    "- **Text.** Titles, goals, opening messages, facts, behaviour, cards, the staff decision, seller messages and",
    "  every expectation, citation, obligation and quality citation are the author's, copied by the program,",
    "  character for character.",
]


def main() -> int:
    if (OUT / "FROZEN").exists():
        shown = OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT
        print(f"{shown.as_posix()} is frozen: nothing is written")
        return 1
    candidates = selected_candidates()
    if tuple(candidates) != SELECTED:
        raise ValueError("CONVERSION does not list the manifest's candidates in its order")
    drawn = json.loads(SUBSET.read_text(encoding="utf-8"))["situations"]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.toml"):
        old.unlink()
    log = [*INTRO, "", *RULES, "", "## Scenario by scenario"]
    for sid, conversion in CONVERSION.items():
        candidate = candidates[sid]
        text, notes = convert(candidate, drawn[sid], conversion)
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
