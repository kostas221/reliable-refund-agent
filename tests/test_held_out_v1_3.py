"""The comparison set of v1.3 is the author's 39 selected candidates, converted without adding anything
(docs/held-out-v1.3/protocol.md, section 4; docs/held-out-v1.3/conversion-log.md).

Each file must be the selected block whose SHA-256 the manifest records, word for word, with only the numbers of the
real Olist orders drawn for it and the dates the conversion log describes. The rules every scenario shares (the policy
checks against the policy code, the arithmetic, what the simulated customer sees) run in tests/test_scenarios.py.
"""

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime

import pytest

from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import SPLIT_DIRS, check_frozen, frozen_hashes, load_split

SET = load_split("held_out_v1_3")
DOCS = REPO_ROOT / "docs" / "held-out-v1.3"
MANIFEST = json.loads((DOCS / "selected-39-manifest.json").read_text(encoding="utf-8"))
# Written for development, not the copies of held-out scenarios, which keep their source's template
DEVELOPMENT_TEMPLATES = {s.template for s in load_split("development") if not s.derived_from}
OLIST = REPO_ROOT / "data" / "olist"
SUBSET = json.loads((OLIST / "subset-v1.3.json").read_text(encoding="utf-8"))
EARLIER = ("subset.json", "subset-v1.1.json", "subset-v1.2.json", "subset-stress-v1.2.json")
# The selection by group (docs/held-out-v1.3/selected-39-index.md): 6 required handoffs, then 3 clarifications.
SELECTED = {
    "eligible": ["H401", "H402", "H403", "H404", "H405", "H406", "H407", "H409", "H410", "H411", "H412", "H414"]
    + ["H415", "H416"],
    "ineligible": ["H420", "H421", "H422", "H424", "H425", "H426", "H427", "H428"],
    "attack": ["H432", "H433", "H435", "H436", "H438", "H440", "H441", "H442"],
    "clarification_handoff": ["H461", "H462", "H464", "H465", "H466", "H468", "H469", "H471", "H472"],
}


def _converter():
    path = REPO_ROOT / "scripts" / "convert_held_out_v1_3.py"
    spec = importlib.util.spec_from_file_location("convert_held_out_v1_3", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


CONVERTER = _converter()
SOURCES = CONVERTER.selected_candidates()


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SET[0].now.tzinfo)


def test_the_set_is_the_thirty_nine_selected_candidates_in_their_groups():
    assert [s.id for s in SET] == [c["id"] for c in MANIFEST["candidates"]]
    assert Counter(s.category for s in SET) == {group: len(ids) for group, ids in SELECTED.items()}
    for scenario in SET:
        assert scenario.id in SELECTED[scenario.category], scenario.id
    assert list(CONVERTER.SELECTED) == [sid for ids in SELECTED.values() for sid in ids]
    handoffs = Counter(s.expected.handoff for s in SET if s.category == "clarification_handoff")
    assert handoffs == {"required": 6, "forbidden": 3}  # the manifest's composition
    assert "H463" not in CONVERTER.SELECTED  # removed by the owner, not replaced


def test_each_block_is_the_authors_word_for_word_and_the_one_the_manifest_records():
    answers = {s["path"]: (REPO_ROOT / s["path"]).read_bytes() for s in MANIFEST["sources"]}
    for source in MANIFEST["sources"]:
        assert hashlib.sha256(answers[source["path"]]).hexdigest() == source["sha256"], source["path"]
    text = (DOCS / "selected-39-author-specifications.md").read_bytes().decode("utf-8")
    blocks = CONVERTER.FENCE.findall(text)
    assert len(blocks) == 39
    for block, listed in zip(blocks, MANIFEST["candidates"], strict=True):
        assert hashlib.sha256(block.encode("utf-8")).hexdigest() == listed["author_block_sha256"], listed["id"]
        assert block.rstrip("\n") in answers[listed["source_path"]].decode("utf-8"), listed["id"]


def test_a_block_changed_by_one_character_is_refused(monkeypatch, tmp_path):
    text = (DOCS / "selected-39-author-specifications.md").read_text(encoding="utf-8")
    changed = tmp_path / "specifications.md"
    changed.write_text(text.replace("Wooden salad bowl", "Wooden salad bowls", 1), encoding="utf-8", newline="\n")
    monkeypatch.setattr(CONVERTER, "SPECIFICATIONS", changed)
    with pytest.raises(ValueError, match="H401: the block is not the one the manifest records"):
        CONVERTER.selected_candidates()


def test_files_are_named_by_id_and_template_and_share_no_template_with_development():
    names = sorted(path.name for path in SPLIT_DIRS["held_out_v1_3"].glob("*.toml"))
    assert names == sorted(f"{s.id}-{s.template}.toml" for s in SET)
    templates = [s.template for s in SET]
    assert len(set(templates)) == len(templates)
    assert not set(templates) & DEVELOPMENT_TEMPLATES
    assert max(len(t) for t in templates) <= 60  # a full path stays under Windows' 260 characters
    for scenario in SET:
        assert CONVERTER.slug(scenario.title, limit=1000).startswith(scenario.template), scenario.id


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_every_word_of_the_source_is_kept(scenario):
    source = SOURCES[scenario.id]
    assert (scenario.title, scenario.category) == (source["title"], source["category"])
    role, customer = source["customer"], scenario.customer
    assert (customer.goal, customer.opening_message) == (role["goal"], role["opening_message"])
    assert [(f.text, f.reveal) for f in customer.facts] == [(f["text"], f["reveal"]) for f in role.get("facts", [])]
    assert list(customer.behaviour) == role.get("behaviour", [])
    cards = role["cards"]
    assert (customer.cards.other, customer.cards.after_confirming) == (cards["other"], cards["after_confirming"])
    assert (scenario.staff.decision, scenario.staff.note) == (source["staff"]["decision"], source["staff"]["note"])
    products = [u["product"] for o in source["orders"] for u in o["units"]]
    assert [u.product for o in scenario.fixture.orders for u in o.units] == products
    messages = [o.get("seller_message", "") for o in source["orders"]]
    assert [o.seller_message_untrusted for o in scenario.fixture.orders] == messages
    # The units by the source's names: the author numbers them across the orders.
    unit = {u.id.rsplit("-", 1)[1]: u for o in scenario.fixture.orders for u in o.units}
    assert list(unit) == [u["key"] for o in source["orders"] for u in o["units"]]
    names = {u.id: name for name, u in unit.items()}
    expected, wrote = scenario.expected, source["expected"]
    assert [names[u] for u in expected.refunded_units] == wrote["refunded_units"]
    assert expected.refund_amount_minor == CONVERTER.paid_sum(
        wrote["refund_amount"], {k: u.paid_minor for k, u in unit.items()}
    )
    for key in ("last_proposal_status", "handoff", "handoff_origins", "cites", "communication", "forbidden"):
        value = getattr(expected, key)
        assert (list(value) if isinstance(value, tuple) else value) == wrote[key], (scenario.id, key)
    assert list(expected.quality_cites) == wrote["quality_cites"]
    assert dict(expected.obligations) == wrote["obligations"]
    confirms = role.get("confirms")
    if confirms:
        assert [names[u] for u in customer.confirms.units] == confirms["units"]
    else:
        assert customer.confirms is None
    history = [r.units for r in scenario.fixture.past_refunds]
    assert [[names[u] for u in units] for units in history] == [r["units"] for r in source.get("past_refunds", [])]
    proposals = [([names[u] for u in p.units], p.status) for p in scenario.fixture.past_proposals]
    assert proposals == [(p["units"], p["status"]) for p in source.get("past_proposals", [])]


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_another_customers_order_belongs_to_someone_else_and_is_hidden_from_the_agent(scenario):
    source = SOURCES[scenario.id]
    customer = scenario.customer.id
    for order, wrote in zip(scenario.fixture.orders, source["orders"], strict=True):
        mine = wrote["owner"] == "customer"
        assert (order.customer == customer) == mine, order.id
        assert (order.id in scenario.agent_visible_orders) == mine, order.id
    assert len(scenario.fixture.customers) == 1 + any(o["owner"] == "other" for o in source["orders"])


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_every_order_is_the_olist_order_drawn_for_it(scenario):
    drawn = SUBSET["situations"][scenario.id]
    source = SOURCES[scenario.id]
    discounts = [u["discount"] for o in source["orders"] for u in o["units"]]
    units = [u for o in scenario.fixture.orders for u in o.units]
    assert [o.olist_order for o in scenario.fixture.orders] == [o["order_id"] for o in drawn]
    items = [i for o in drawn for i in o["items"]]
    for order, olist, wrote in zip(scenario.fixture.orders, drawn, source["orders"], strict=True):
        assert order.status == olist["status"], order.id
        assert [u.olist_item for u in order.units] == [i["order_item_id"] for i in olist["items"]], order.id
        stated = [(p.method, p.installments, p.amount_minor) for p in order.payments]
        real = [(p["method"], p["installments"], p["amount_minor"]) for p in olist["payments"]]
        if (scenario.id, wrote["key"]) in CONVERTER.SPLIT_PAYMENTS:
            # The one synthetic payment of the set: Olist's total, in the two records the author named.
            assert sum(p.amount_minor for p in order.payments) == sum(p["amount_minor"] for p in olist["payments"])
            assert sorted(p.method for p in order.payments) == sorted(wrote["shape"]["payments"])
        else:
            assert stated == real, order.id
        # The dates move as one block: from purchase to delivery takes as long as it did at Olist.
        if olist["delivered_at"] is not None and order.delivered_at is not None:
            taken = olist_time(olist["delivered_at"]) - olist_time(olist["purchased_at"])
            assert order.delivered_at - order.purchased_at == taken, order.id
    for unit, item, discount in zip(units, items, discounts, strict=True):
        # What was paid is the Olist price; a listed price above it comes only from the source's own words.
        assert (unit.paid_minor, unit.shipping_minor) == (item["price_minor"], item["freight_minor"]), unit.id
        assert unit.price_minor == CONVERTER.listed_price(item["price_minor"], discount, unit.id), unit.id


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_every_drawn_order_has_the_authors_shape_and_ties(scenario):
    drawn = SUBSET["situations"][scenario.id]
    source = SOURCES[scenario.id]
    for olist, wrote in zip(drawn, source["orders"], strict=True):
        shape = wrote["shape"]
        assert olist["status"] == wrote["status"], wrote["key"]
        assert len(olist["items"]) == shape["items"], wrote["key"]
        assert len({i["product_id"] for i in olist["items"]}) == shape["distinct_products"], wrote["key"]
        assert len({i["seller_id"] for i in olist["items"]}) == shape["sellers"], wrote["key"]
        methods = sorted(p["method"] for p in olist["payments"])
        if (scenario.id, wrote["key"]) in CONVERTER.SPLIT_PAYMENTS:
            assert methods == ["credit_card"], wrote["key"]  # drawn by card, split by the conversion
        else:
            assert methods == sorted(shape["payments"]), wrote["key"]
    keys = [o["key"] for o in source["orders"]]
    for olist, wrote in zip(drawn, source["orders"], strict=True):
        tie = wrote.get("tie", "")
        if not tie:
            continue
        target = drawn[keys.index(tie.split(" as ")[1].split(",")[0])]
        if tie.startswith("same product as"):
            assert olist["items"][0]["product_id"] == target["items"][0]["product_id"], tie
        else:
            assert tie.startswith("same category as") and tie.endswith("another product"), tie
            assert olist["items"][0]["category"] == target["items"][0]["category"], tie
    if any(o.get("tie", "").startswith("same category") for o in source["orders"]):
        assert len({o["items"][0]["product_id"] for o in drawn}) == len(drawn)


def test_no_order_of_an_earlier_set_is_used_again():
    earlier = {
        o["order_id"]
        for name in EARLIER
        for orders in json.loads((OLIST / name).read_text(encoding="utf-8"))["situations"].values()
        for o in orders
    }
    drawn = [o["order_id"] for orders in SUBSET["situations"].values() for o in orders]
    assert len(drawn) == len(set(drawn)) == 63
    assert not set(drawn) & earlier
    assert list(SUBSET["situations"]) == list(CONVERTER.SELECTED)


@pytest.mark.parametrize("scenario", SET, ids=lambda s: s.id)
def test_the_source_timing_is_kept_to_the_hour(scenario):
    source = SOURCES[scenario.id]
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
    units = scenario.fixture.unit_by_id()
    for refund, wrote in zip(scenario.fixture.past_refunds, source.get("past_refunds", []), strict=True):
        assert scenario.now - refund.committed_at == CONVERTER.before_now(wrote["when"], "refund")
        assert all(units[u].received_back_at < refund.committed_at for u in refund.units), scenario.id
    for proposal, wrote in zip(scenario.fixture.past_proposals, source.get("past_proposals", []), strict=True):
        assert scenario.now - proposal.created_at == CONVERTER.before_now(wrote["when"], proposal.id)
        assert all(units[u].received_back_at < proposal.created_at for u in proposal.units), scenario.id


def test_the_deadline_the_author_set_hours_away_is_exact():
    # H472: "delivered 29 days and 12 hours before now", so the 30 days end 12 hours after now.
    h472 = next(s for s in SET if s.id == "H472")
    deadline = h472.fixture.orders[0].delivered_at + 30 * CONVERTER.DAYS
    assert (deadline - h472.now).total_seconds() == 12 * 3600


def test_times_in_days_and_hours_are_read_both_ways():
    assert CONVERTER.before_now("delivered 29 days and 12 hours before now", "x") == CONVERTER.DAYS * 29.5
    assert CONVERTER.before_now("delivered 3 days 6 hours before now", "x") == CONVERTER.DAYS * 3.25
    assert CONVERTER.before_now("received back 1 day before now", "x") == CONVERTER.DAYS
    with pytest.raises(ValueError, match="no 'N days before now'"):
        CONVERTER.before_now("last week", "x")


def test_a_split_payment_keeps_the_total_and_the_card_instalments():
    split = CONVERTER.split_payment({"method": "credit_card", "amount_minor": 6411, "installments": 5}, ("a", "b"))
    assert split == [
        {"method": "a", "amount_minor": 3206, "installments": 5},
        {"method": "b", "amount_minor": 3205, "installments": 1},
    ]


def test_a_discount_is_the_paid_price_times_the_stated_share_rounded_half_up():
    assert CONVERTER.listed_price(4590, "listed 20% above what was paid", "x") == 5508
    assert CONVERTER.listed_price(1005, "listed 10% above what was paid", "x") == 1106  # 1105.5 rounds up
    with pytest.raises(ValueError, match="no conversion for the discount"):
        CONVERTER.listed_price(1005, "an order-wide discount", "x")


def test_the_converter_writes_nothing_once_the_set_is_frozen(monkeypatch, tmp_path, capsys):
    (tmp_path / "FROZEN").write_text("frozen\n", encoding="utf-8")
    (tmp_path / "H401-x.toml").write_text("kept\n", encoding="utf-8")
    monkeypatch.setattr(CONVERTER, "OUT", tmp_path)
    assert CONVERTER.main() == 1
    assert "is frozen: nothing is written" in capsys.readouterr().out
    assert (tmp_path / "H401-x.toml").read_text(encoding="utf-8") == "kept\n"


def test_the_set_is_frozen_and_every_file_matches():
    directory = SPLIT_DIRS["held_out_v1_3"]
    check_frozen(directory)
    assert sorted(frozen_hashes(directory)) == sorted(path.name for path in directory.glob("*.toml"))
    assert len(frozen_hashes(directory)) == 39


def test_the_converter_writes_nothing_to_the_frozen_set(capsys):
    directory = SPLIT_DIRS["held_out_v1_3"]
    before = {path: path.read_bytes() for path in directory.glob("*")}
    log = (DOCS / "conversion-log.md").read_bytes()
    assert CONVERTER.main() == 1
    assert "scenarios/held-out-v1.3 is frozen: nothing is written" in capsys.readouterr().out
    assert {path: path.read_bytes() for path in directory.glob("*")} == before
    assert (DOCS / "conversion-log.md").read_bytes() == log
