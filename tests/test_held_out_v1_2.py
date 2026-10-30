"""The held-out set of v1.2 is the author's 19 kept candidates, and the stress set Claude's 8 stress scenarios, both
converted without adding anything (docs/held-out-v1.2/protocol.md, section 4; plan change log, 2026-10-30).

Each file must be its source's latest version, word for word, with only the numbers of the real Olist order drawn
for it and the dates the conversion log describes. The rules every scenario shares (the policy checks against the
policy code, the arithmetic, what the simulated customer sees) run in tests/test_scenarios.py.
"""

import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime

import pytest

from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import SPLIT_DIRS, check_frozen, frozen_hashes, load_split

HELD_OUT = load_split("held_out_v1_2")
STRESS = load_split("stress_v1_2")
DEVELOPMENT_TEMPLATES = {s.template for s in load_split("development")}
OLIST = REPO_ROOT / "data" / "olist"
SUBSETS = {
    "held_out_v1_2": json.loads((OLIST / "subset-v1.2.json").read_text(encoding="utf-8")),
    "stress_v1_2": json.loads((OLIST / "subset-stress-v1.2.json").read_text(encoding="utf-8")),
}
EARLIER = [json.loads((OLIST / name).read_text(encoding="utf-8")) for name in ("subset.json", "subset-v1.1.json")]
# The kept candidates in each group, in the author's order (docs/held-out-v1.2/set-aside.md, section 9.2).
KEPT = {
    "eligible": ["H102", "H108", "H113", "H116", "H233", "H235", "H238", "H240", "H241", "H245"],
    "ineligible": ["H196", "H255", "H261", "H314"],
    "attack": ["H143"],
    "clarification_handoff": ["H281", "H286", "H300", "H355"],
}


def _converter():
    path = REPO_ROOT / "scripts" / "convert_held_out_v1_2.py"
    spec = importlib.util.spec_from_file_location("convert_held_out_v1_2", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


CONVERTER = _converter()
SOURCES = {
    "held_out_v1_2": CONVERTER.latest_candidates(),
    "stress_v1_2": CONVERTER.latest_candidates((CONVERTER.STRESS_SOURCE,)),
}
BOTH = HELD_OUT + STRESS


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=HELD_OUT[0].now.tzinfo)


def test_the_set_is_the_nineteen_kept_candidates_in_their_groups():
    assert sorted(s.id for s in HELD_OUT) == sorted(sid for ids in KEPT.values() for sid in ids)
    assert Counter(s.category for s in HELD_OUT) == {group: len(ids) for group, ids in KEPT.items()}
    for scenario in HELD_OUT:
        assert scenario.id in KEPT[scenario.category], scenario.id
    assert list(CONVERTER.KEPT) == [sid for ids in KEPT.values() for sid in ids]


def test_the_stress_set_is_the_eight_written_and_none_of_situation_one():
    assert [s.id for s in STRESS] == [f"S0{n}" for n in range(1, 9)]
    assert sorted(SOURCES["stress_v1_2"]) == [s.id for s in STRESS]


@pytest.mark.parametrize("split", ["held_out_v1_2", "stress_v1_2"])
def test_files_are_named_by_id_and_template_and_share_no_template_with_development(split):
    scenarios = load_split(split)
    names = sorted(path.name for path in SPLIT_DIRS[split].glob("*.toml"))
    assert names == sorted(f"{s.id}-{s.template}.toml" for s in scenarios)
    assert not {s.template for s in scenarios} & DEVELOPMENT_TEMPLATES


@pytest.mark.parametrize("scenario", BOTH, ids=lambda s: s.id)
def test_every_word_of_the_source_is_kept(scenario):
    source = SOURCES[scenario.split][scenario.id]
    assert (scenario.title, scenario.category) == (source["title"], source["category"])
    role, customer = source["customer"], scenario.customer
    assert (customer.goal, customer.opening_message) == (role["goal"], role["opening_message"])
    assert [(f.text, f.reveal) for f in customer.facts] == [(f["text"], f["reveal"]) for f in role.get("facts", [])]
    assert list(customer.behaviour) == role.get("behaviour", [])
    cards = role.get("cards", {"other": "decline", "after_confirming": "keep"})
    assert (customer.cards.other, customer.cards.after_confirming) == (cards["other"], cards["after_confirming"])
    assert (scenario.staff.decision, scenario.staff.note) == (
        source["staff"]["decision"],
        source["staff"].get("note", ""),
    )
    products = [u["product"] for o in source["orders"] for u in o["units"]]
    assert [u.product for o in scenario.fixture.orders for u in o.units] == products
    # The units by the source's names: u1 is the first unit of the first order, and so on.
    unit = {u.id.rsplit("-", 1)[1]: u for o in scenario.fixture.orders for u in o.units}
    names = {u.id: name for name, u in unit.items()}
    expected, wrote = scenario.expected, source["expected"]
    assert [names[u] for u in expected.refunded_units] == wrote["refunded_units"]
    assert expected.refund_amount_minor == CONVERTER.paid_sum(
        wrote["refund_amount"], {k: u.paid_minor for k, u in unit.items()}
    )
    for key in ("last_proposal_status", "handoff", "handoff_origins", "cites", "communication", "forbidden"):
        value = getattr(expected, key)
        assert (list(value) if isinstance(value, tuple) else value) == wrote[key], (scenario.id, key)
    assert list(expected.quality_cites) == wrote.get("quality_cites", [])
    assert dict(expected.obligations) == wrote.get("obligations", {})
    confirms = role.get("confirms")
    if confirms:
        assert [names[u] for u in customer.confirms.units] == confirms["units"]
    else:
        assert customer.confirms is None
    history = [r.units for r in scenario.fixture.past_refunds]
    assert [[names[u] for u in units] for units in history] == [r["units"] for r in source.get("past_refunds", [])]
    proposals = [([names[u] for u in p.units], p.status) for p in scenario.fixture.past_proposals]
    assert proposals == [(p["units"], p["status"]) for p in source.get("past_proposals", [])]


@pytest.mark.parametrize("scenario", BOTH, ids=lambda s: s.id)
def test_every_order_is_the_olist_order_drawn_for_it(scenario):
    drawn = SUBSETS[scenario.split]["situations"][scenario.id]
    source = SOURCES[scenario.split][scenario.id]
    discounts = [u.get("discount", "none") for o in source["orders"] for u in o["units"]]
    units = [u for o in scenario.fixture.orders for u in o.units]
    assert [o.olist_order for o in scenario.fixture.orders] == [o["order_id"] for o in drawn]
    items = [i for o in drawn for i in o["items"]]
    for order, olist in zip(scenario.fixture.orders, drawn, strict=True):
        assert order.status == olist["status"], order.id
        assert [u.olist_item for u in order.units] == [i["order_item_id"] for i in olist["items"]], order.id
        stated = [(p.method, p.installments, p.amount_minor) for p in order.payments]
        assert stated == [(p["method"], p["installments"], p["amount_minor"]) for p in olist["payments"]], order.id
        # The dates move as one block: from purchase to delivery takes as long as it did at Olist.
        if olist["delivered_at"] is not None and order.delivered_at is not None:
            taken = olist_time(olist["delivered_at"]) - olist_time(olist["purchased_at"])
            assert order.delivered_at - order.purchased_at == taken, order.id
    for unit, item, discount in zip(units, items, discounts, strict=True):
        # What was paid is the Olist price; a listed price above it comes only from the source's own words.
        assert (unit.paid_minor, unit.shipping_minor) == (item["price_minor"], item["freight_minor"]), unit.id
        assert unit.price_minor == CONVERTER.listed_price(item["price_minor"], discount, unit.id), unit.id


def test_a_discount_is_the_paid_price_times_the_stated_share_rounded_half_up():
    assert CONVERTER.listed_price(4590, "listed 20% above what was paid", "x") == 5508
    assert CONVERTER.listed_price(1005, "listed 10% above what was paid", "x") == 1106  # 1105.5 rounds up
    assert CONVERTER.listed_price(1005, "none", "x") == 1005
    with pytest.raises(ValueError, match="no conversion for the discount"):
        CONVERTER.listed_price(1005, "an order-wide discount", "x")


def test_no_order_of_an_earlier_held_out_set_is_used_again():
    earlier = {o["order_id"] for subset in EARLIER for orders in subset["situations"].values() for o in orders}
    v1_2 = [o["order_id"] for orders in SUBSETS["held_out_v1_2"]["situations"].values() for o in orders]
    stress = [o["order_id"] for orders in SUBSETS["stress_v1_2"]["situations"].values() for o in orders]
    assert len(v1_2) == len(set(v1_2)) == 22
    assert len(stress) == len(set(stress)) == 9
    assert not set(v1_2) & earlier
    assert not set(stress) & (earlier | set(v1_2))


@pytest.mark.parametrize("scenario", BOTH, ids=lambda s: s.id)
def test_the_source_timing_is_kept_to_the_hour(scenario):
    source = SOURCES[scenario.split][scenario.id]
    for order, wrote in zip(scenario.fixture.orders, source["orders"], strict=True):
        moment, before = CONVERTER.anchor(wrote, scenario.id)
        fixed = order.delivered_at if moment == "delivered" else order.purchased_at
        assert scenario.now - fixed == before, order.id
    returns = [u["returned"] for o in source["orders"] for u in o["units"]]
    for unit, returned in zip([u for o in scenario.fixture.orders for u in o.units], returns, strict=True):
        if returned == "not received back":
            assert unit.received_back_at is None, unit.id
        else:
            assert scenario.now - unit.received_back_at == CONVERTER.before_now(returned, unit.id), unit.id
    for refund, wrote in zip(scenario.fixture.past_refunds, source.get("past_refunds", []), strict=True):
        assert scenario.now - refund.committed_at == CONVERTER.before_now(wrote["when"], "refund")
        # A unit is refunded only after it came back (the second fact told to the author).
        units = scenario.fixture.unit_by_id()
        assert all(units[u].received_back_at < refund.committed_at for u in refund.units), scenario.id
    for proposal, wrote in zip(scenario.fixture.past_proposals, source.get("past_proposals", []), strict=True):
        assert scenario.now - proposal.created_at == CONVERTER.before_now(wrote["when"], proposal.id)
        units = scenario.fixture.unit_by_id()
        assert all(units[u].received_back_at < proposal.created_at for u in proposal.units), scenario.id


def test_the_deadlines_the_author_set_hours_away_are_exact():
    by_id = {s.id: s for s in HELD_OUT}
    for sid, hours in (("H233", 8), ("H241", 10)):
        deadline = by_id[sid].fixture.orders[0].delivered_at + 30 * CONVERTER.DAYS
        assert (deadline - by_id[sid].now).total_seconds() == hours * 3600, sid


@pytest.mark.parametrize(("split", "count"), [("held_out_v1_2", 19), ("stress_v1_2", 8)])
def test_the_set_is_frozen_and_every_file_matches(split, count):
    directory = SPLIT_DIRS[split]
    check_frozen(directory)
    assert sorted(frozen_hashes(directory)) == sorted(path.name for path in directory.glob("*.toml"))
    assert len(frozen_hashes(directory)) == count


def test_the_converter_writes_nothing_once_the_sets_are_frozen(capsys):
    directories = [SPLIT_DIRS["held_out_v1_2"], SPLIT_DIRS["stress_v1_2"]]
    before = {path: path.read_bytes() for directory in directories for path in directory.glob("*")}
    assert CONVERTER.main() == 1
    out = capsys.readouterr().out
    assert out.count("is frozen: nothing is written") == 2
    assert {path: path.read_bytes() for directory in directories for path in directory.glob("*")} == before
