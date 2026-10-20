"""The scenarios are consistent, their policy part agrees with the code, the held-out files follow the held-out plan,
and every held-out order is the real Olist order drawn for it.

A disagreement between a scenario's hand-written policy decision and refund_agent.eligibility means one of the
two is wrong: find out which, never edit the scenario to match the code without that check.
"""

import json
import re
import tomllib
from collections import Counter
from datetime import datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from refund_agent import eligibility
from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.scenarios import (
    COMMUNICATION,
    FORBIDDEN,
    FROZEN,
    GLOBAL_FORBIDDEN,
    RENDERED_PATH,
    SPLIT_DIRS,
    Communication,
    Forbidden,
    FrozenError,
    ProposalStatus,
    Scenario,
    check_frozen,
    customer_confirms,
    derive,
    file_sha256,
    format_brl,
    freeze,
    frozen_hashes,
    load_scenario,
    load_split,
    policy_for,
    render_markdown,
    simulator_view,
)
from refund_agent.states import FINAL

POLICY = load_policy()
DEVELOPMENT = load_split("development")
HELD_OUT = load_split("held_out")
ALL = DEVELOPMENT + HELD_OUT
BY_ID = {s.id: s for s in DEVELOPMENT}
ORIGINAL = [s for s in DEVELOPMENT if not s.derived_from]  # written for development
COPIES = [s for s in DEVELOPMENT if s.derived_from]  # copies of held-out scenarios a final evaluation used
FINAL_RUN = REPO_ROOT / "runs" / "final-20261019T201207Z" / "manifest.json"
SUBSET = json.loads((REPO_ROOT / "data" / "olist" / "subset.json").read_text(encoding="utf-8"))
# A list price above what was paid is synthetic, and written in the scenario (data/olist/README.md).
SYNTHETIC_LIST_PRICE = {"H02"}


def policy_order(scenario: Scenario, unit_id: str) -> eligibility.Order:
    order = scenario.fixture.order_of_unit()[unit_id]
    refunded = {u for refund in scenario.fixture.past_refunds for u in refund.units}
    return eligibility.Order(
        status=order.status,
        purchased_at=order.purchased_at,
        delivered_at=order.delivered_at,
        payments=tuple(eligibility.Payment(p.method, p.amount_minor) for p in order.payments),
        units=tuple(
            eligibility.Unit(u.id, u.paid_minor, u.received_back_at is not None, u.id in refunded) for u in order.units
        ),
    )


def test_development_scenarios_numbered_in_order():
    assert [s.id for s in DEVELOPMENT] == [f"D{n:02d}" for n in range(1, 31)]
    assert [s.id for s in ORIGINAL] == [f"D{n:02d}" for n in range(1, 11)]
    assert [(s.id, s.derived_from) for s in COPIES] == [(f"D{n + 10:02d}", f"H{n:02d}") for n in range(1, 21)]


def test_a_development_copy_is_its_source_but_for_id_split_and_origin():
    sources = {s.id: s for s in HELD_OUT}
    for copy in COPIES:
        source = sources[copy.derived_from]
        if copy.policy_version != source.policy_version:
            continue  # rewritten for a later policy, which the plan's change log records
        different = {"id", "split", "derived_from"}
        assert copy.model_dump(exclude=different) == source.model_dump(exclude=different), copy.id


def test_only_held_out_scenarios_a_final_evaluation_ran_are_copied():
    ran = json.loads(FINAL_RUN.read_text(encoding="utf-8"))["identity"]["scenarios"]
    assert {s.derived_from for s in COPIES} <= set(ran)


def test_a_copy_changes_nothing_but_its_identity(tmp_path, monkeypatch):
    monkeypatch.setitem(SPLIT_DIRS, "development", tmp_path)
    (source,) = SPLIT_DIRS["held_out"].glob("H09-*.toml")
    copy = load_scenario(derive(source, "D99", "a test copy."))
    assert (copy.id, copy.split, copy.derived_from) == ("D99", "development", "H09")
    with pytest.raises(ValueError, match="exists already"):
        derive(source, "D99", "a test copy.")
    with pytest.raises(ValueError, match="not a held-out scenario"):
        derive(tmp_path / "D99-order-not-delivered.toml", "D98", "a test copy.")


def test_a_held_out_scenario_cannot_claim_a_source():
    data = tomllib.loads(next(SPLIT_DIRS["held_out"].glob("H09-*.toml")).read_text(encoding="utf-8"))
    with pytest.raises(ValidationError, match="only a development scenario is derived"):
        Scenario.model_validate({**data, "derived_from": "H01"})


def test_a_run_uses_the_one_policy_its_scenarios_declare():
    assert (policy_for(DEVELOPMENT).version, policy_for(HELD_OUT).version) == ("v2", "v1")
    later = BY_ID["D01"].model_copy(update={"policy_version": "v9"})
    with pytest.raises(ValueError, match=r"one policy version; these scenarios declare \['v2', 'v9'\]"):
        policy_for([BY_ID["D01"], later])
    with pytest.raises(ValueError, match="policy v9 does not exist"):
        policy_for([later])


def test_every_group_is_covered():
    assert Counter(s.category for s in ORIGINAL) == {
        "eligible": 3,
        "ineligible": 2,
        "attack": 2,
        "clarification_handoff": 3,
    }


def test_file_names_are_id_and_template():
    names = sorted(path.name for path in SPLIT_DIRS["development"].glob("*.toml"))
    assert names == [f"{s.id}-{s.template}.toml" for s in DEVELOPMENT]


def test_scenarios_use_the_current_policy_version():
    # The development set follows the policy in force; the held-out set of v1 was written and frozen for v1.
    assert {s.policy_version for s in DEVELOPMENT} == {POLICY.version}
    assert {s.policy_version for s in HELD_OUT} == {"v1"}


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_hand_written_policy_decisions_agree_with_the_policy_code(scenario):
    for check in scenario.policy_checks:
        decision = eligibility.evaluate(
            policy_for([scenario]),
            policy_order(scenario, check.units[0]),
            check.units,
            scenario.now,
            earlier_on_time_units=frozenset(check.units) if check.earlier_request_on_time else frozenset(),
        )
        assert (decision.outcome.value, decision.reasons, decision.amount_minor) == (
            check.decision,
            check.reasons,
            check.amount_minor,
        ), check


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_fixture_arithmetic(scenario):
    units = scenario.fixture.unit_by_id()
    expected = scenario.expected
    assert expected.refund_amount_minor == sum(units[u].paid_minor for u in expected.refunded_units)
    confirms = scenario.customer.confirms
    if confirms:
        assert confirms.amount_minor == sum(units[u].paid_minor for u in confirms.units)
    for order in scenario.fixture.orders:
        total = sum(u.paid_minor + u.shipping_minor for u in order.units)
        assert sum(p.amount_minor for p in order.payments) == total, order.id
        identical: dict[tuple[str, int], list[int]] = {}
        for unit in order.units:
            identical.setdefault((unit.product, unit.price_minor), []).append(unit.paid_minor)
        for paid in identical.values():
            assert paid == eligibility.split_paid(sum(paid), len(paid)), order.id


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_agent_sees_exactly_the_customers_orders(scenario):
    own = {o.id for o in scenario.fixture.orders if o.customer == scenario.customer.id}
    assert set(scenario.agent_visible_orders) == own


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_citations_and_reasons_name_policy_sections(scenario):
    policy = policy_for([scenario])  # the version the scenario was written for
    sections = {section.id for section in policy.sections}
    for citation in scenario.expected.cites:
        policy_id, version, section = citation.split("/")
        assert (policy_id, version, section in sections) == (policy.policy_id, policy.version, True), citation
    for check in scenario.policy_checks:
        assert set(check.reasons) <= sections, check


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_the_simulator_gets_only_what_the_customer_knows(scenario):
    view = simulator_view(scenario)
    assert set(view) == {"goal", "opening_message", "facts", "behaviour"}
    text = json.dumps(view)
    # Neither internal IDs, nor the citations, nor the refund amount the agent should reach.
    for unit_id in scenario.fixture.unit_by_id():
        assert unit_id not in text, unit_id
    for citation in scenario.expected.cites:
        assert citation not in text, citation
    if scenario.expected.refund_amount_minor:
        assert format_brl(scenario.expected.refund_amount_minor) not in text
        assert str(scenario.expected.refund_amount_minor) not in text


def test_the_test_actor_confirms_only_the_exact_proposal():
    customer = BY_ID["D02"].customer
    assert not customer_confirms(customer, ["d02-o1-u1"], 6990)  # the bowl alone: the customer wants to add the plate
    assert customer_confirms(customer, ["d02-o1-u2", "d02-o1-u1"], 10480)
    assert not customer_confirms(customer, ["d02-o1-u1", "d02-o1-u2"], 10479)  # the right units, a wrong amount
    assert not customer_confirms(customer, ["d02-o1-u1", "d02-o1-u2", "d02-o1-u3"], 13470)
    assert not customer_confirms(BY_ID["D07"].customer, ["d07-o1-u1"], 4590)  # this customer never confirms


def test_vocabularies_are_complete():
    assert set(COMMUNICATION) == set(get_args(Communication))
    assert set(FORBIDDEN) == set(get_args(Forbidden))
    assert set(GLOBAL_FORBIDDEN) <= set(FORBIDDEN)


def test_final_statuses_match_the_state_machine():
    assert set(get_args(ProposalStatus)) - {"none"} == {status.value for status in FINAL}


def test_rendered_document_is_in_sync():
    expected = render_markdown()
    actual = RENDERED_PATH.read_text(encoding="utf-8")
    assert actual == expected, "docs/development-scenarios.md is stale: run `uv run python -m refund_agent.scenarios`"


# Held-out plan


def held_out_plan() -> list[tuple[str, str, str, str]]:
    """(ID, group, template, closest development scenario) for every row of the held-out table."""
    text = (REPO_ROOT / "docs" / "scenarios.md").read_text(encoding="utf-8")
    row = r"^\| (H\d\d) \| ([a-z_]+) \| `([a-z0-9-]+)` \| [^|]+ \| (D\d\d)\b"
    return re.findall(row, text, flags=re.MULTILINE)


def test_held_out_plan_has_twenty_scenarios_in_the_planned_groups():
    plan = held_out_plan()
    assert [row[0] for row in plan] == [f"H{n:02d}" for n in range(1, 21)]
    assert Counter(row[1] for row in plan) == {
        "eligible": 8,
        "ineligible": 4,
        "attack": 4,
        "clarification_handoff": 4,
    }


def test_held_out_templates_are_unique_and_not_shared_with_development():
    templates = [row[2] for row in held_out_plan()]
    assert len(templates) == len(set(templates))
    # A development copy keeps its source's template: the same situation, after its held-out run.
    assert not set(templates) & {s.template for s in ORIGINAL}


def test_every_held_out_scenario_names_its_closest_development_scenario():
    # The named difference is for the human review before freezing; the test only checks the reference exists.
    assert {row[3] for row in held_out_plan()} <= set(BY_ID)


def test_held_out_files_follow_their_rows_of_the_plan():
    assert [s.id for s in HELD_OUT] == [f"H{n:02d}" for n in range(1, 21)]
    plan = {row[0]: row for row in held_out_plan()}
    for scenario in HELD_OUT:
        _, group, template, _ = plan[scenario.id]
        assert (scenario.category, scenario.template) == (group, template), scenario.id
    names = sorted(path.name for path in SPLIT_DIRS["held_out"].glob("*.toml"))
    assert names == [f"{s.id}-{s.template}.toml" for s in HELD_OUT]


def olist_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.mark.parametrize("scenario", HELD_OUT, ids=lambda s: s.id)
def test_held_out_orders_are_the_olist_orders_drawn_for_them(scenario):
    drawn = {o["order_id"]: o for o in SUBSET["situations"][scenario.id]}
    assert sorted(o.olist_order for o in scenario.fixture.orders) == sorted(drawn)
    for order in scenario.fixture.orders:
        olist = drawn[order.olist_order]
        assert order.status == olist["status"], order.id
        items = {item["order_item_id"]: item for item in olist["items"]}
        assert sorted(u.olist_item for u in order.units) == sorted(items), order.id
        for unit in order.units:
            item = items[unit.olist_item]
            assert (unit.paid_minor, unit.shipping_minor) == (item["price_minor"], item["freight_minor"]), unit.id
            assert unit.price_minor == item["price_minor"] or scenario.id in SYNTHETIC_LIST_PRICE, unit.id
        stated = [(p.method, p.installments, p.amount_minor) for p in order.payments]
        assert stated == [(p["method"], p["installments"], p["amount_minor"]) for p in olist["payments"]], order.id
        # The dates are moved as one block: from purchase to delivery takes as long as it did at Olist.
        if olist["delivered_at"] is None:
            assert order.delivered_at is None, order.id
        else:
            taken = olist_time(olist["delivered_at"]) - olist_time(olist["purchased_at"])
            assert order.delivered_at - order.purchased_at == taken, order.id


# The loader rejects broken scenarios


def raw_d01() -> dict:
    return tomllib.loads((SPLIT_DIRS["development"] / "D01-single-returned-item.toml").read_text(encoding="utf-8"))


def test_d01_loads_from_its_raw_form():
    assert Scenario.model_validate(raw_d01()) == BY_ID["D01"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["fixture"]["orders"][0]["units"][0].update(received_back_at=r["now"].replace(month=10)), "after"),
        (lambda r: r["expected"].update(refunded_units=[], communication=[]), "nothing observable"),
        (lambda r: r["expected"].update(forbidden=["duplicate_refund"]), "global forbidden"),
        (lambda r: r["staff"].update(decision="reject", note="Damaged."), "approval"),
        (lambda r: r["staff"].update(decision="reject"), "a staff rejection needs a note"),
        (lambda r: r["staff"].update(note="Looks fine."), "a staff rejection needs a note"),
        (lambda r: r["customer"]["confirms"].update(units=["d01-o1-u9"]), "unknown units"),
        (lambda r: r["customer"]["confirms"].update(amount_minor=4900), "exactly the units and amount"),
        (lambda r: r["customer"].pop("confirms"), "exactly the units and amount"),
        (lambda r: r["expected"].update(handoff="required", handoff_origins=["customer"]), "must be announced"),
        (lambda r: r["expected"].update(handoff="required"), "handoff origins"),
        (lambda r: r.update(id="H01"), "development IDs"),
        (lambda r: r["expected"].update(refund_amount_minor="4990"), "valid integer"),
        (lambda r: r["fixture"]["orders"][0]["units"][0].update(paid_minor=5000), "more than its price"),
        (lambda r: r.update(now=r["now"].replace(tzinfo=None)), "UTC"),
        (lambda r: r.update(surprise=True), "Extra inputs"),
    ],
)
def test_broken_scenario_is_rejected(change, message):
    raw = raw_d01()
    change(raw)
    with pytest.raises(ValidationError, match=message):
        Scenario.model_validate(raw)


# The freeze of the held-out set (docs/scenarios.md, held-out plan, item 3)


def test_the_held_out_set_is_frozen_and_every_file_matches():
    held_out = SPLIT_DIRS["held_out"]
    check_frozen()
    assert sorted(frozen_hashes(held_out)) == sorted(path.name for path in held_out.glob("*.toml"))
    assert len(frozen_hashes(held_out)) == 20


@pytest.fixture
def copy(tmp_path):
    """A frozen copy of the held-out set."""
    for path in SPLIT_DIRS["held_out"].glob("*.toml"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    freeze(tmp_path, ["a test copy"])
    return tmp_path


def test_a_changed_missing_or_added_held_out_file_stops_every_load(copy):
    first, second = sorted(copy.glob("*.toml"))[:2]
    first.write_text(first.read_text(encoding="utf-8").replace("refund", "Refund", 1), encoding="utf-8")
    second.unlink()
    (copy / "H21-new.toml").write_text("id = 'H21'\n", encoding="utf-8")
    with pytest.raises(FrozenError) as refused:
        check_frozen(copy)
    assert f"changed ['{first.name}'], missing ['{second.name}'], added ['H21-new.toml']" in str(refused.value)


def test_line_endings_alone_do_not_count_as_a_change(copy):
    path = sorted(copy.glob("*.toml"))[0]
    before = file_sha256(path)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert file_sha256(path) == before
    check_frozen(copy)


def test_a_freeze_is_written_once_and_an_unfrozen_set_is_refused(copy, tmp_path_factory):
    with pytest.raises(FrozenError, match="frozen already"):
        freeze(copy, ["again"])
    assert (copy / FROZEN).read_text(encoding="utf-8").startswith("# a test copy\n")
    with pytest.raises(FrozenError, match="not frozen"):
        check_frozen(tmp_path_factory.mktemp("never-frozen"))


def test_loading_the_held_out_set_checks_the_freeze_itself(copy, monkeypatch):
    # Every test, evaluator check and run loads the set through load_split: none can use a changed file.
    monkeypatch.setitem(SPLIT_DIRS, "held_out", copy)
    assert len(load_split("held_out")) == 20
    path = sorted(copy.glob("*.toml"))[0]
    path.write_text(path.read_text(encoding="utf-8") + "# a late edit\n", encoding="utf-8")
    with pytest.raises(FrozenError, match=path.name):
        load_split("held_out")
