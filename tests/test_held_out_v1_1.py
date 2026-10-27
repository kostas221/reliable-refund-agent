"""The held-out set of v1.1 is the author's 20 kept candidates, converted without adding anything
(docs/held-out-v1.1/protocol.md, section 4).

Each file must be the author's latest version of its candidate, word for word, with only the numbers of the real Olist
order drawn for it and the dates the conversion log describes. The rules every scenario shares (the policy checks
against the policy code, the arithmetic, what the simulated customer sees) run in tests/test_scenarios.py.
"""

import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timedelta

import pytest

from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import SPLIT_DIRS, check_frozen, frozen_hashes, load_split

SET = load_split("held_out_v1_1")
# A development copy keeps its source's template (D43 to D62 are this set's, copied on 2026-10-27, after its run).
DEVELOPMENT_TEMPLATES = {s.template for s in load_split("development") if not s.derived_from}
SUBSET = json.loads((REPO_ROOT / "data" / "olist" / "subset-v1.1.json").read_text(encoding="utf-8"))
V1_SUBSET = json.loads((REPO_ROOT / "data" / "olist" / "subset.json").read_text(encoding="utf-8"))
# The kept candidates in each group, in the author's order (docs/held-out-v1.1/set-aside.md, section 10).
KEPT = {
    "eligible": ["H26", "H28", "H29", "H30", "H50", "H52", "H55", "H74"],
    "ineligible": ["H35", "H58", "H60", "H61"],
    "attack": ["H40", "H41", "H42", "H63"],
    "clarification_handoff": ["H47", "H72", "H77", "H80"],
}


def _converter():
    path = REPO_ROOT / "scripts" / "convert_held_out_v1_1.py"
    spec = importlib.util.spec_from_file_location("convert_held_out_v1_1", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


CONVERTER = _converter()
AUTHOR = CONVERTER.latest_candidates()


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SET[0].now.tzinfo)


def test_the_set_is_the_twenty_kept_candidates_in_their_groups():
    assert sorted(s.id for s in SET) == sorted(sid for ids in KEPT.values() for sid in ids)
    assert Counter(s.category for s in SET) == {group: len(ids) for group, ids in KEPT.items()}
    for scenario in SET:
        assert scenario.id in KEPT[scenario.category], scenario.id
    names = sorted(path.name for path in SPLIT_DIRS["held_out_v1_1"].glob("*.toml"))
    assert names == [f"{s.id}-{s.template}.toml" for s in SET]
    assert not {s.template for s in SET} & DEVELOPMENT_TEMPLATES


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_every_word_of_the_author_is_kept(scenario):
    author = AUTHOR[scenario.id]
    assert (scenario.title, scenario.category) == (author["title"], author["category"])
    role, customer = author["customer"], scenario.customer
    assert (customer.goal, customer.opening_message) == (role["goal"], role["opening_message"])
    assert [(f.text, f.reveal) for f in customer.facts] == [(f["text"], f["reveal"]) for f in role.get("facts", [])]
    assert list(customer.behaviour) == role.get("behaviour", [])
    assert (customer.cards.other, customer.cards.after_confirming) == (
        role["cards"]["other"],
        role["cards"]["after_confirming"],
    )
    assert (scenario.staff.decision, scenario.staff.note) == (
        author["staff"]["decision"],
        author["staff"].get("note", ""),
    )
    products = [u["product"] for o in author["orders"] for u in o["units"]]
    assert [u.product for o in scenario.fixture.orders for u in o.units] == products
    # The units by the author's names: u1 is the first unit of the first order, and so on.
    unit = {u.id.rsplit("-", 1)[1]: u for o in scenario.fixture.orders for u in o.units}
    names = {u.id: name for name, u in unit.items()}
    expected, wrote = scenario.expected, author["expected"]
    assert [names[u] for u in expected.refunded_units] == wrote["refunded_units"]
    assert expected.refund_amount_minor == CONVERTER.paid_sum(
        wrote["refund_amount"], {k: u.paid_minor for k, u in unit.items()}
    )
    for key in ("last_proposal_status", "handoff", "handoff_origins", "cites", "communication", "forbidden"):
        value = getattr(expected, key)
        assert (list(value) if isinstance(value, tuple) else value) == wrote[key], (scenario.id, key)
    confirms = role.get("confirms")
    if confirms:
        assert [names[u] for u in customer.confirms.units] == confirms["units"]
    else:
        assert customer.confirms is None
    history = [(r.units, r.committed_at) for r in scenario.fixture.past_refunds]
    assert [[names[u] for u in units] for units, _ in history] == [r["units"] for r in author.get("past_refunds", [])]
    proposals = [([names[u] for u in p.units], p.status) for p in scenario.fixture.past_proposals]
    assert proposals == [(p["units"], p["status"]) for p in author.get("past_proposals", [])]


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_every_order_is_the_olist_order_drawn_for_it(scenario):
    drawn = SUBSET["situations"][scenario.id]
    assert [o.olist_order for o in scenario.fixture.orders] == [o["order_id"] for o in drawn]
    for order, olist in zip(scenario.fixture.orders, drawn, strict=True):
        assert order.status == olist["status"], order.id
        assert [u.olist_item for u in order.units] == [i["order_item_id"] for i in olist["items"]], order.id
        for unit, item in zip(order.units, olist["items"], strict=True):
            # No discount in any kept candidate: what was paid is the Olist price, and so is the price.
            assert (unit.price_minor, unit.paid_minor, unit.shipping_minor) == (
                item["price_minor"],
                item["price_minor"],
                item["freight_minor"],
            ), unit.id
        stated = [(p.method, p.installments, p.amount_minor) for p in order.payments]
        assert stated == [(p["method"], p["installments"], p["amount_minor"]) for p in olist["payments"]], order.id
        # The dates move as one block: from purchase to delivery takes as long as it did at Olist.
        if olist["delivered_at"] is None:
            assert order.delivered_at is None, order.id
        else:
            taken = olist_time(olist["delivered_at"]) - olist_time(olist["purchased_at"])
            assert order.delivered_at - order.purchased_at == taken, order.id


def test_no_order_of_v1s_held_out_set_is_used_again():
    v1 = {o["order_id"] for orders in V1_SUBSET["situations"].values() for o in orders}
    v1_1 = [o["order_id"] for orders in SUBSET["situations"].values() for o in orders]
    assert len(v1_1) == len(set(v1_1)) == 21
    assert not set(v1_1) & v1


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_the_author_timing_is_kept_to_the_hour(scenario):
    # Every event "N days before now" lies exactly N x 24 hours before now (conversion log, rules).
    conversion = CONVERTER.CONVERSION[scenario.id]
    for order, anchor, olist in zip(
        scenario.fixture.orders, conversion.anchors, SUBSET["situations"][scenario.id], strict=True
    ):
        if anchor.moment == "delivered":
            assert scenario.now - order.delivered_at == anchor.before, order.id
        elif anchor.moment == "purchased":
            assert scenario.now - order.purchased_at == anchor.before, order.id
        else:  # recorded as delivered with no delivery time: timed by the date Olist promised at purchase
            promised = olist_time(olist["estimated_delivery_at"]) - olist_time(olist["purchased_at"])
            assert scenario.now - order.purchased_at == anchor.before + promised, order.id
    # Returns, earlier refunds and earlier proposals, each as the author timed it.
    author = AUTHOR[scenario.id]
    returns = [u["returned"] for o in author["orders"] for u in o["units"]]
    for unit, returned in zip([u for o in scenario.fixture.orders for u in o.units], returns, strict=True):
        if returned == "not received back":
            assert unit.received_back_at is None, unit.id
        else:
            assert scenario.now - unit.received_back_at == CONVERTER.days_before(returned, unit.id), unit.id
    for refund, wrote in zip(scenario.fixture.past_refunds, author.get("past_refunds", []), strict=True):
        assert scenario.now - refund.committed_at == CONVERTER.days_before(wrote["when"], "refund")
    for proposal, wrote in zip(scenario.fixture.past_proposals, author.get("past_proposals", []), strict=True):
        assert scenario.now - proposal.created_at == CONVERTER.days_before(wrote["when"], proposal.id)


def test_h26_is_six_hours_before_the_deadline():
    (h26,) = [s for s in SET if s.id == "H26"]
    assert h26.fixture.orders[0].delivered_at + timedelta(days=30) - h26.now == timedelta(hours=6)


def test_h77_is_delivered_with_no_delivery_time():
    (h77,) = [s for s in SET if s.id == "H77"]
    (order,) = h77.fixture.orders
    assert (order.status, order.delivered_at) == ("delivered", None)


def test_the_set_is_frozen_and_every_file_matches():
    directory = SPLIT_DIRS["held_out_v1_1"]
    check_frozen(directory)
    assert sorted(frozen_hashes(directory)) == sorted(path.name for path in directory.glob("*.toml"))
    assert len(frozen_hashes(directory)) == 20


def test_the_converter_writes_nothing_once_the_set_is_frozen(capsys):
    before = {path.name: path.read_bytes() for path in SPLIT_DIRS["held_out_v1_1"].glob("*")}
    assert CONVERTER.main() == 1
    assert "is frozen: nothing is written" in capsys.readouterr().out
    assert {path.name: path.read_bytes() for path in SPLIT_DIRS["held_out_v1_1"].glob("*")} == before
