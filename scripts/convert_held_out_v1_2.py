"""Writes the held-out set of v1.2 from the author's answers (docs/held-out-v1.2/protocol.md, section 4.2).

    uv run python scripts/convert_held_out_v1_2.py

For each of the 19 kept candidates (docs/held-out-v1.2/set-aside.md, section 9.2) it takes the author's latest
version, copies its text by program (title, role, facts, behaviour, cards, staff decision, expectations, citations,
obligations and quality citations, word for word), fills in the numbers of the Olist order drawn for it
(data/olist/subset-v1.2.json) and the dates, and writes scenarios/held-out-v1.2/<ID>-<template>.toml and
docs/held-out-v1.2/conversion-log.md. Everything the format needs that the author did not state is in CONVERSION and
the rules below, and is listed in the log. It refuses to write once the set is frozen.
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
DOCS = ROOT / "docs" / "held-out-v1.2"
# Later versions replace earlier ones: the second answer corrected 43 candidates of the first.
ANSWERS = ("author-output.md", "author-output-2.md", "author-output-3.md", "author-output-4.md")
SUBSET = ROOT / "data" / "olist" / "subset-v1.2.json"
OUT = ROOT / "scenarios" / "held-out-v1.2"
LOG = DOCS / "conversion-log.md"
SPLIT = "held_out_v1_2"

# One clock for every scenario, as in v1.1: the author times each event relative to "now", never to a date.
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
STAFF = ("rui", "Rui Costa", "rui.costa@shop.example.test")  # the scripted staff member, as in v1 and v1.1
DAYS = timedelta(days=1)

Check = tuple[tuple[str, ...], str, tuple[str, ...]]  # (units, decision, reasons): Claude's reading of the policy


@dataclass(frozen=True)
class Conversion:
    customer: str  # a synthetic name: Olist has none
    policy_checks: tuple[Check, ...]


ELIGIBLE = "eligible"
CONVERSION = {
    # eligible
    "H102": Conversion("Livia Batista", ((("u1", "u2"), ELIGIBLE, ()), (("u1", "u2", "u3"), "refused", ("return",)))),
    "H108": Conversion("Otavio Ribeiro", ((("u3",), ELIGIBLE, ()), (("u1",), "refused", ("return",)))),
    "H113": Conversion("Bianca Teixeira", ((("u1",), ELIGIBLE, ()),)),
    "H116": Conversion("Mateus Carvalho", ((("u2", "u3"), ELIGIBLE, ()), (("u1",), "refused", ("remaining",)))),
    "H233": Conversion("Clara Fontes", ((("u1",), ELIGIBLE, ()), (("u2",), ELIGIBLE, ()))),
    "H235": Conversion("Diego Sampaio", ((("u1", "u2"), ELIGIBLE, ()),)),
    "H238": Conversion("Yasmin Lacerda", ((("u3",), ELIGIBLE, ()), (("u1", "u2", "u3"), "refused", ("remaining",)))),
    "H240": Conversion("Henrique Matos", ((("u2",), ELIGIBLE, ()), (("u1",), ELIGIBLE, ()))),
    "H241": Conversion("Alice Brandao", ((("u1",), ELIGIBLE, ()), (("u2",), "refused", ("return",)))),
    "H245": Conversion(
        "Rodrigo Peixoto",
        (
            (("u1", "u2"), ELIGIBLE, ()),
            (("u3",), "refused", ("return",)),
            (("u4",), "refused", ("eligible-orders", "return")),
        ),
    ),
    # ineligible
    "H196": Conversion("Leticia Amaral", ((("u1",), ELIGIBLE, ()), (("u2",), "refused", ("window",)))),
    "H255": Conversion(
        "Fabio Guedes", ((("u1",), "refused", ("window", "return")), (("u2",), "refused", ("window", "remaining")))
    ),
    "H261": Conversion("Natalia Pinheiro", ((("u1",), "refused", ("remaining",)), (("u2",), ELIGIBLE, ()))),
    "H314": Conversion(
        "Caua Rezende",
        ((("u1",), "refused", ("remaining",)), (("u2",), "refused", ("return",)), (("u3",), ELIGIBLE, ())),
    ),
    # attack
    "H143": Conversion("Joana Esteves", ((("u1",), ELIGIBLE, ()),)),
    # clarification_handoff
    "H281": Conversion(
        "Pedro Albuquerque",
        ((("u1",), ELIGIBLE, ()), (("u2",), ELIGIBLE, ()), (("u3",), "refused", ("return",))),
    ),
    "H286": Conversion("Sabrina Moura", ((("u1", "u2"), ELIGIBLE, ()),)),
    "H300": Conversion(
        "Igor Valente", ((("u1",), ELIGIBLE, ()), (("u1", "u2"), ELIGIBLE, ()), (("u3",), "refused", ("return",)))
    ),
    "H355": Conversion("Tatiana Quintela", ((("u1", "u2"), ELIGIBLE, ()),)),
}
KEPT = tuple(CONVERSION)  # in the groups' order, each group in the author's order (set-aside.md, section 9.2)

# The stress scenarios Claude wrote in the author's format (stress-scenarios.md), converted the same way.
STRESS_SOURCE = "stress-scenarios.md"
STRESS_SUBSET = ROOT / "data" / "olist" / "subset-stress-v1.2.json"
STRESS_OUT = ROOT / "scenarios" / "stress-v1.2"
STRESS_LOG = DOCS / "stress-conversion-log.md"
STRESS_SPLIT = "stress_v1_2"
STRESS_CONVERSION = {
    "S01": Conversion("Renan Coutinho", ((("u1",), ELIGIBLE, ()),)),
    "S02": Conversion("Priscila Andrade", ((("u1",), ELIGIBLE, ()),)),
    "S03": Conversion("Murilo Santana", ((("u1",), ELIGIBLE, ()),)),
    "S04": Conversion("Elisa Cordeiro", ((("u1",), ELIGIBLE, ()), (("u2",), "refused", ("return",)))),
    "S05": Conversion("Vitor Medeiros", ((("u1",), ELIGIBLE, ()), (("u2",), ELIGIBLE, ()))),
    "S06": Conversion("Giovana Rocha", ((("u1",), ELIGIBLE, ()), (("u2",), ELIGIBLE, ()))),
    "S07": Conversion("Simone Prates", ((("u1",), ELIGIBLE, ()), (("u2",), "refused", ("return",)))),
    "S08": Conversion(
        "Arthur Leme", ((("u2",), ELIGIBLE, ()), (("u1",), ELIGIBLE, ()), (("u3",), "refused", ("return",)))
    ),
}

TIMED = re.compile(r"(\d+) days?(?: (\d+) hours?)? before now")
LISTED = re.compile(r"listed (\d+)% above what was paid")


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


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def before_now(text: str, what: str) -> timedelta:
    """The first "N days [H hours] before now" in the author's words."""
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


def latest_candidates(names: tuple[str, ...] = ANSWERS) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for name in names:
        text = (DOCS / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        for block in re.findall(r"```toml\n(.*?)```", text, flags=re.S):
            candidate = tomllib.loads(block)
            latest[candidate["id"]] = {**candidate, "_source": name}
    return latest


def paid_sum(expression: str, paid: dict[str, int]) -> int:
    """The author's symbolic amount: "0", "paid(u1)" or "paid(u1)+paid(u2)"."""
    if expression.strip() == "0":
        return 0
    terms = [t.strip() for t in expression.split("+")]
    keys = [re.fullmatch(r"paid\((u\d+)\)", t) for t in terms]
    if not all(keys):
        raise ValueError(f"not a sum of paid amounts: {expression!r}")
    return sum(paid[k.group(1)] for k in keys)


def convert(
    candidate: dict,
    olist: list[dict],
    conversion: Conversion,
    split: str = SPLIT,
    label: str = "The author's candidate",
    subset: Path = SUBSET,
) -> tuple[str, list[str]]:
    sid, low = candidate["id"], candidate["id"].lower()
    first = conversion.customer.split()[0].lower()
    customer_id = f"{low}-{first}"
    email = ".".join(conversion.customer.lower().split()) + "@example.test"
    notes = [f"customer {conversion.customer} <{email}> (synthetic)"]
    unit_id, paid = {}, {}
    orders = candidate["orders"]
    if len(orders) != len(olist):
        raise ValueError(f"{sid}: {len(orders)} orders, {len(olist)} drawn")

    header = [f"# {candidate['title']}."]
    log = (STRESS_LOG if split == STRESS_SPLIT else LOG).relative_to(ROOT).as_posix()
    header.append(f"# {label} {sid} ({candidate['_source']}), converted by scripts/convert_held_out_v1_2.py;")
    header.append(f"# every choice the text did not state is in {log}.")
    order_blocks = []
    for n, (order, record) in enumerate(zip(orders, olist, strict=True), start=1):
        if order["owner"] != "customer":
            raise ValueError(f"{sid}: an order of another customer needs its own conversion")
        oid = f"{low}-o{n}"
        moment, before = anchor(order, sid)
        purchased = olist_time(record["purchased_at"])
        delivered = olist_time(record["delivered_at"]) if record["delivered_at"] else None
        fixed = {"delivered": delivered, "purchased": purchased}[moment]
        if fixed is None:
            raise ValueError(f"{sid}: order {n} has no {moment} time")
        shift = (NOW - before) - fixed  # the order's dates move as one block
        hours = f" {before.seconds // 3600} h" if before.seconds else ""
        notes.append(
            f"order {order['key']} = Olist {record['order_id']}: moved by {shift.days} days and "
            f"{shift.seconds // 3600} h {shift.seconds % 3600 // 60} min so that its {moment} time lies "
            f'{before.days} days{hours} before now (the author: "{order["timing"]}")'
        )
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
            f"# Olist order {record['order_id']} ({subset.relative_to(ROOT).as_posix()}): {len(items)} item(s), "
            + "; ".join(
                f"{p['method']} {brl(p['amount_minor'])} in {p['installments']} instalment(s)"
                for p in record["payments"]
            )
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
    cards = role.get("cards", {})
    other, after = cards.get("other", "decline"), cards.get("after_confirming", "keep")
    customer.append(f'cards = {{ other = "{other}", after_confirming = "{after}" }}')
    if "cards" not in role:
        notes.append('cards: the author stated none; the defaults (other "decline", after_confirming "keep")')
    staff = candidate["staff"]
    staff_lines = ["", "[staff]", f'decision = "{staff["decision"]}"']
    if staff.get("note"):
        staff_lines.append(f"note = {toml_string(staff['note'])}")

    checks = []
    for units, decision, reasons in conversion.policy_checks:
        amount = sum(paid[u] for u in units) if decision == ELIGIBLE else 0
        checks += [
            "",
            "[[policy_checks]]",
            f"units = {toml_list(unit_id[u] for u in units)}",
            f'decision = "{decision}"',
        ]
        if reasons:
            checks.append(f"reasons = {toml_list(reasons)}")
        if amount:
            checks.append(f"amount_minor = {amount}")

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
        f'split = "{split}"',
        f'category = "{candidate["category"]}"',
        f'template = "{slug(candidate["title"])}"',
        'policy_version = "v2"',
        f"now = {toml_time(NOW)}  # {candidate['now']}",
        f"agent_visible_orders = {toml_list(own)}",
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


RULES = [
    "## Rules for every scenario",
    "",
    f"- **The clock.** Every scenario's now is {toml_time(NOW)}, as in v1.1. The author times each event relative to",
    '  now, never to a date; an event "N days [H hours] before now" is placed exactly that long before it.',
    "- **The orders.** Each Olist order's dates move as one block, so that the moment the author times (its delivery,",
    "  or its purchase for an order still on its way) lies exactly as long before now as the author says; from",
    "  purchase to delivery takes as long as it did at Olist. The format has no field for when an order was shipped,",
    "  so the author's words for it stay beside the order as a comment.",
    "- **The draw.** Each order has the shape the author stated (status, items, distinct products, sellers, payment",
    "  methods), drawn by `uv run python -m refund_agent.olist v1.2`, never an order of v1's or v1.1's set.",
    "- **History.** An earlier refund or proposal keeps the author's units, status and time; a refund's receipt",
    "  number is synthetic. The format has no field for when an earlier proposal expired or stopped being valid.",
    "- **Units and amounts.** The author's units u1, u2, ... are the order's Olist items in their order. What a unit",
    "  paid is its Olist price, its shipping is its Olist freight, and the payment records are Olist's, instalments",
    "  included. The author's symbolic amounts (`paid(u1)+paid(u2)`) are summed from these. Where the author wrote",
    '  "listed N% above what was paid", the listed price is the paid price times (100 + N) / 100, rounded half up',
    "  to the centavo; Olist has no discounts, so this price is synthetic and named in the scenario.",
    "  Product names are the author's; the Olist category, which nobody in a conversation sees, is in the log.",
    "- **Clocks the author wrote twice.** Where `now` and an order's `timing` disagreed, the order's `timing` is",
    "  used, as the owner told the author (set-aside.md, section 6); the 19 kept candidates were corrected so that",
    "  they agree.",
    "- **People.** Each customer has a synthetic name and e-mail; the staff member is Rui Costa, as in v1.",
    "- **IDs.** `hNNN-o1`, `hNNN-o1-u1`, `hNNN-p1` for an earlier proposal, `R-HNNN-0001` for an earlier refund's",
    "  receipt; the template is the author's title in lower case with hyphens.",
    "- **Policy checks** are Claude's reading of the policy for the units each scenario turns on; a test compares",
    "  them with the policy code. They are for the technical checks, not for grading the agent.",
    "- **Novel.** The author marked all 19 kept candidates `novel`, so the report of the `novel` candidates is the",
    "  report of the whole set; the scenario format has no field for it.",
    "- **Text.** Titles, goals, opening messages, facts, behaviour, cards, the staff decision and every expectation,",
    "  citation, obligation and quality citation are the author's, copied by the program, character for character.",
]


def write_set(
    out: Path,
    log_path: Path,
    subset: Path,
    names: tuple[str, ...],
    conversions: dict[str, Conversion],
    split: str,
    label: str,
    intro: list[str],
) -> int:
    if (out / "FROZEN").exists():
        print(f"{out.relative_to(ROOT)} is frozen: nothing is written")
        return 1
    candidates = latest_candidates(names)
    drawn = json.loads(subset.read_text(encoding="utf-8"))["situations"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.toml"):
        old.unlink()
    log = [*intro, "", *RULES, "", "## Scenario by scenario"]
    for sid, conversion in conversions.items():
        candidate = candidates[sid]
        text, notes = convert(candidate, drawn[sid], conversion, split, label, subset)
        path = out / f"{sid}-{slug(candidate['title'])}.toml"
        path.write_text(text, encoding="utf-8", newline="\n")
        log += ["", f"### {sid}: {candidate['title']}", "", f"From `{candidate['_source']}`."]
        log += [f"- {note}" for note in notes]
        print(f"wrote {path.relative_to(ROOT).as_posix()}")
    log_path.write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {log_path.relative_to(ROOT).as_posix()}")
    return 0


HELD_OUT_INTRO = [
    "# Held-out v1.2: conversion log",
    "",
    "For the project owner and anyone checking that the scenario files add nothing to the author's candidates:",
    "every value the scenario format needs that the author did not state, scenario by scenario. Generated by",
    "`scripts/convert_held_out_v1_2.py` from the author's latest version of each kept candidate",
    "([set-aside.md](set-aside.md), section 9.2) and the orders drawn for it (`data/olist/subset-v1.2.json`).",
]
STRESS_INTRO = [
    "# Stress scenarios of v1.2: conversion log",
    "",
    "For the project owner: every value the scenario format needs that the stress scenarios",
    "([stress-scenarios.md](stress-scenarios.md), written by Claude) do not state, scenario by scenario. Generated by",
    "`scripts/convert_held_out_v1_2.py` with the same rules as the held-out set, from the orders drawn for them",
    '(`data/olist/subset-stress-v1.2.json`). Where the rules below say "the author", read "Claude".',
]


def main() -> int:
    held_out = write_set(OUT, LOG, SUBSET, ANSWERS, CONVERSION, SPLIT, "The author's candidate", HELD_OUT_INTRO)
    stress = write_set(
        STRESS_OUT,
        STRESS_LOG,
        STRESS_SUBSET,
        (STRESS_SOURCE,),
        STRESS_CONVERSION,
        STRESS_SPLIT,
        "Claude's stress scenario",
        STRESS_INTRO,
    )
    return max(held_out, stress)


if __name__ == "__main__":
    sys.exit(main())
