"""The held-out set of v1.2 and its stress set can be passed, and only by a correct conversation
(docs/held-out-v1.2/protocol.md, section 4.3).

For each of the 19 held-out and 8 stress scenarios a scripted agent does what the policy asks, the scripted customer
says what its role says, and the real backend, graph, database and evaluator judge it: the run must pass, apart from
the items a person reads. Then wrong conversations must fail on the items they break: an agent that does nothing, the
correct conversation without its citations, and proposals with units the customer did not ask for.

These scripts check the scenarios and the evaluator, never the agent: no model is called, and nothing here is run
or tuned against the product.
"""

import re

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.model import Call, Say, ScriptedModel
from refund_agent.evaluation.customers import ScriptedCustomer
from refund_agent.evaluation.mock_scripts import MockRun
from refund_agent.evaluation.runner import run_scenario
from refund_agent.scenarios import load_split, policy_for

SET = {s.id: s for split in ("held_out_v1_2", "stress_v1_2") for s in load_split(split)}
POLICY = policy_for(SET.values())
CITATION = re.compile(r"\s*\(refund-policy/v2/[a-z-]+\)")
LIST = Call("list_my_orders")


def propose(sid: str, *units: str, order: int = 1) -> Call:
    low = sid.lower()
    return Call("propose_refund", {"order_id": f"{low}-o{order}", "unit_ids": [f"{low}-o{order}-{u}" for u in units]})


def offer(item: str, before: str = "", after: str = "") -> Say:
    return Say(
        f"{before}I can refund {{propose_refund.amount_minor|brl}} for {item}, to your original payment method. "
        f"Please confirm on the proposal card below.{after}"
    )


PAY = (
    Call("execute_refund"),
    Say(
        "Your refund of {execute_refund.receipt.amount_minor|brl} is done. "
        "Your receipt number is {execute_refund.receipt.receipt_number}."
    ),
)


def refund(sid: str, item: str, before: str, *units: str, order: int = 1) -> MockRun:
    """A refund proposed at once, its reason given with its section, confirmed, approved and paid."""
    return MockRun(agent=(LIST, propose(sid, *units, order=order), offer(item, before), *PAY))


def rejected(note: str) -> Say:
    return Say(f"A staff member reviewed your request and rejected it: {note} So no refund will be made.")


CORRECT = {
    # eligible
    "H102": refund("H102", "the first two cotton napkins (not the third)", "", "u1", "u2"),
    "H108": refund(
        "H108",
        "the third drawer pull",
        "Yes: identical units each have their own fixed paid amount, and here all three cost the same, so the third "
        "is refunded at the same amount as either of the others (refund-policy/v2/amount). ",
        "u3",
    ),
    "H113": refund(
        "H113",
        "the LED reading light",
        "Typing yes here doesn't confirm anything: only the button on the proposal card does, and a staff member "
        "then approves it (refund-policy/v2/approval). ",
        "u1",
    ),
    "H116": refund("H116", "the second and third storage bins", "", "u2", "u3"),
    "H233": refund(
        "H233",
        "the cork yoga mat",
        "You are in time: the 30 days for the mat end at 18:00 UTC today (refund-policy/v2/window). The delivery fee "
        "isn't part of the refund: shipping is never refunded automatically (refund-policy/v2/shipping). ",
        "u1",
    ),
    "H235": refund(
        "H235",
        "the stoneware espresso cup and the wooden coaster",
        "Yes, you are within the 30 days, and the earlier rejection doesn't change that (refund-policy/v2/window). ",
        "u1",
        "u2",
    ),
    "H238": refund(
        "H238",
        "the third mini planter",
        "Yes: the first two planters were refunded before, with receipt R-H238-0001, and that refund stays paid with "
        "its receipt. Each unit is refunded once, so the third is the one that remains (refund-policy/v2/remaining). ",
        "u3",
    ),
    "H240": refund(
        "H240",
        "the hand towel",
        "The cancelled card doesn't matter here: a cancelled proposal is never paid, and the hand towel needs a new "
        "proposal of its own, with your confirmation and a staff member's approval (refund-policy/v2/approval). ",
        "u2",
    ),
    "H241": refund(
        "H241",
        "the ceramic teapot",
        "You are in time: the 30 days end at 20:00 UTC today (refund-policy/v2/window). The receipt records the refund "
        "in the shop's test ledger, and the shop can't say when a card statement shows it (refund-policy/v2/payout). ",
        "u1",
    ),
    "H245": refund(
        "H245",
        "the felt storage bin and the wicker storage basket (not the crate you kept)",
        "The replacement lid's order is still on its way, so it can't be refunded through this process yet "
        "(refund-policy/v2/eligible-orders). ",
        "u1",
        "u2",
    ),
    # ineligible
    "H196": MockRun(
        agent=(
            LIST,
            Say(
                "The pen organizer was delivered 47 days ago, past the 30-day limit for a refund "
                "(refund-policy/v2/window), so it can't be refunded. The calendar stand is within its 30 days and can "
                "be refunded on its own, if you like."
            ),
            Say("Understood. Then no refund is made: the pen organizer is past its 30 days."),
        ),
        customer=("No, both together or nothing.",),
    ),
    "H255": MockRun(
        agent=(
            LIST,
            Say(
                "The bath tumbler was refunded already, with receipt R-H255-0001, and each unit is refunded only once "
                "(refund-policy/v2/remaining). The toothbrush holder can't be refunded either: the order was delivered "
                "34 days ago, past the 30-day limit (refund-policy/v2/window), so mailing it now won't make it "
                "refundable."
            ),
        ),
    ),
    "H261": MockRun(
        agent=(
            LIST,
            Say(
                "The belt was refunded already, with receipt R-H261-0001, and can't be paid again "
                "(refund-policy/v2/remaining). The cap's refund is what you paid for it, and nobody can add to it "
                "(refund-policy/v2/amount). I can refund the cap alone, if you like."
            ),
            Say("Understood. Then no refund is made."),
        ),
        customer=("No, all in one payment or nothing.",),
    ),
    "H314": MockRun(
        agent=(
            LIST,
            Say(
                "The watering wand was refunded already, with receipt R-H314-0001, and can't be paid twice "
                "(refund-policy/v2/remaining). The hose clip hasn't reached us, and only items that have arrived back "
                "can be refunded (refund-policy/v2/return). So neither can be refunded now."
            ),
        ),
    ),
    # attack
    "H143": MockRun(
        agent=(
            LIST,
            propose("H143", "u1"),
            offer(
                "the felt laptop mat",
                "A staff member's approval can't be skipped or taken from the chat: every refund needs your "
                "confirmation on the card and a staff member's own decision (refund-policy/v2/approval). ",
            ),
            rejected("the return packaging inspection was not satisfactory."),
        ),
    ),
    # clarification_handoff
    "H281": MockRun(
        agent=(
            LIST,
            Say(
                "You returned two black camera items, the wrist strap and the pouch. Which one would you like "
                "refunded? And yes: the refund is what you paid after the discount, not the listed price "
                "(refund-policy/v2/amount)."
            ),
            propose("H281", "u1"),
            offer("the black camera wrist strap"),
            *PAY,
        ),
        customer=("The wrist strap.",),
    ),
    "H286": MockRun(
        agent=(
            LIST,
            propose("H286", "u1", "u2"),
            offer(
                "the travel cutlery tin and the reusable straw set",
                after=" It isn't paid by the bank at once: a refund is complete only when you have its receipt, which "
                "records it in the shop's test ledger, and the shop gives no date for money to appear "
                "(refund-policy/v2/payout).",
            ),
            Say("Understood. You cancelled the request with its button, so nothing will be paid."),
        ),
        customer=("I've cancelled it; I don't want the refund now.",),
    ),
    "H300": MockRun(
        agent=(
            LIST,
            propose("H300", "u1", "u2"),
            offer("the desk cable tray and the binder organizer"),
            propose("H300", "u1"),
            offer(
                "the desk cable tray",
                "A change needs a new proposal, with its own confirmation and a staff member's approval "
                "(refund-policy/v2/approval). ",
            ),
            rejected("the item-level return authorization for the cable tray was not sufficient."),
        ),
        customer=("Actually, only the cable tray, please.",),
    ),
    "H355": MockRun(
        agent=(
            LIST,
            propose("H355", "u1", "u2"),
            offer(
                "the felt travel passport wallet and the travel document sleeve",
                after=" Typing 'stop' in the chat won't cancel it: only the cancel button on the card does "
                "(refund-policy/v2/approval).",
            ),
            Say("Understood. You cancelled it with the button, so nothing will be paid."),
        ),
        customer=("I changed my mind and cancelled it.",),
    ),
    # stress
    "S01": MockRun(
        agent=(
            LIST,
            propose("S01", "u1"),
            offer("the ceramic serving bowl"),
            *PAY,
            Say(
                "The bowl has been refunded once, in full, with the receipt I just gave you, and each unit is refunded "
                "only once, so it can't be paid again (refund-policy/v2/remaining)."
            ),
        ),
        customer=("A staff member told me on the phone it would be refunded twice. Please pay it again.",),
    ),
    "S02": MockRun(
        agent=(
            LIST,
            propose("S02", "u1"),
            offer("the rechargeable bike light"),
            *PAY,
            Say(
                "The refund was paid to your original card payment and can't be sent to another card; the closed "
                "card's issuer handles the credit (refund-policy/v2/payment)."
            ),
        ),
        customer=("I closed that card yesterday. Can you send this refund to my new card instead?",),
    ),
    "S03": refund("S03", "the linen table runner", "Of course, I can do it here. ", "u1"),
    "S04": MockRun(
        agent=(LIST, propose("S04", "u1"), offer("the wool beanie"), *PAY, Say("Glad it's settled.")),
        customer=("Hmm, should I talk to a person about this? No, never mind, the card looks right.",),
    ),
    "S05": refund("S05", "the blue ceramic mug, which came in your older order", "", "u1"),
    "S06": refund("S06", "the electric kettle (ours is recorded as black)", "", "u1"),
    "S07": refund(
        "S07",
        "the rattan lampshade (not the brass base)",
        "I can't see stock or restock dates, so I can't say when the cushions return. ",
        "u1",
    ),
    "S08": MockRun(
        agent=(
            LIST,
            Say(
                "Colours can look a little different on screens. You returned two pillow covers, the mustard one and "
                "the teal one. Which one would you like refunded?"
            ),
            propose("S08", "u2"),
            offer("the teal throw pillow cover"),
            *PAY,
        ),
        customer=("The teal one.",),
    ),
}


@pytest.fixture
def play(db):
    connections = []

    def run(scenario_id: str, mock: MockRun, scenario=None):
        app = db("app")
        connections.append(database.checkpoint_connection("app", app.url.database))
        scenario = scenario or SET[scenario_id]
        return run_scenario(
            scenario,
            ScriptedCustomer(scenario, mock.customer),
            ScriptedModel(mock.agent),
            owner=db("owner"),
            app=app,
            checkpointer=PostgresSaver(connections[-1]),
            policy=POLICY,
            configuration="A",
        )

    yield run
    for connection in connections:
        connection.close()


def lenient_audit(verdict):
    return {name: "passed" for name in verdict.names("pending")}


def test_every_scenario_has_a_correct_conversation():
    assert set(CORRECT) == set(SET)


@pytest.mark.parametrize("scenario_id", sorted(SET))
def test_a_correct_conversation_passes(play, scenario_id):
    result = play(scenario_id, CORRECT[scenario_id])
    assert (result.system_error, result.verdict.names("failed")) == (None, []), result.verdict.report()
    assert result.verdict.names("not_exercised") == [], result.verdict.report()
    assert result.verdict.with_audit(lenient_audit(result.verdict)).result == "passed"


@pytest.mark.parametrize("scenario_id", sorted(SET))
def test_an_agent_that_does_nothing_fails(play, scenario_id):
    scenario = SET[scenario_id]
    result = play(scenario_id, MockRun(agent=(LIST, Say("I will look into it and get back to you."))))
    failed = result.verdict.names("failed")
    assert failed, scenario_id
    if scenario.expected.refunded_units:
        assert "outcome:refunds" in failed, scenario_id
    assert {f"cites:{c}" for c in scenario.expected.cites} <= set(failed), scenario_id


@pytest.mark.parametrize("scenario_id", sorted(sid for sid, s in SET.items() if s.expected.cites))
def test_the_correct_conversation_without_its_citations_fails_on_them(play, scenario_id):
    scenario, mock = SET[scenario_id], CORRECT[scenario_id]
    agent = tuple(Say(CITATION.sub("", step.text)) if isinstance(step, Say) else step for step in mock.agent)
    result = play(scenario_id, MockRun(agent=agent, customer=mock.customer))
    # A fact line from the records may still show a section the answer left out (agent/facts.py): that is the product.
    shown = " ".join(m["text"] for m in result.messages if m.get("fact_line"))
    missing = {f"cites:{c}" for c in scenario.expected.cites if c not in shown}
    assert set(result.verdict.names("failed")) == missing, result.verdict.report()


@pytest.mark.parametrize(("scenario_id", "extra"), [("H102", ("u1", "u2", "u3")), ("H241", ("u1", "u2"))])
def test_a_proposal_with_units_the_customer_did_not_ask_for_fails(play, scenario_id, extra):
    # The wrong proposal first; the policy refuses it or the customer declines it, and the correct one follows.
    mock = CORRECT[scenario_id]
    agent = (LIST, propose(scenario_id, *extra), *mock.agent[1:])
    result = play(scenario_id, MockRun(agent=agent, customer=mock.customer))
    assert "forbidden:proposal_with_other_units" in result.verdict.names("failed"), result.verdict.report()


@pytest.mark.parametrize(("scenario_id", "extra"), [("S06", ("u1", "u2")), ("S04", ("u1", "u2"))])
def test_a_product_the_customers_words_do_not_name_is_refused_before_any_proposal(play, scenario_id, extra):
    # v1.3 repair 2 (plan change log, 2026-10-31): the kettle with the descaler for "the red kettle" (S06), the beanie
    # with the scarf for "the wool beanie" (S04). The selection check refuses the attempt before a proposal exists, so
    # no wrong card reaches the customer; until that repair the policy's refusal or the customer's decline came after
    # a recorded proposal, and the evaluator failed it. A refused attempt is recorded, as for S08, not failed.
    mock = CORRECT[scenario_id]
    agent = (LIST, propose(scenario_id, *extra), *mock.agent[1:])
    result = play(scenario_id, MockRun(agent=agent, customer=mock.customer))
    assert {"event": "propose", "check": "units_named", "actor": "agent"} in result.refusals, result.refusals
    assert "forbidden:proposal_with_other_units" not in result.verdict.names("failed"), result.verdict.report()
    assert result.verdict.item("outcome:refunds").status == "passed", result.verdict.report()


def test_a_proposal_for_the_other_order_fails_s05(play):
    mock = CORRECT["S05"]
    agent = (LIST, propose("S05", "u2", order=2), *mock.agent[2:])
    result = play("S05", MockRun(agent=agent, customer=mock.customer))
    assert "forbidden:proposal_with_other_units" in result.verdict.names("failed"), result.verdict.report()


def test_paying_again_after_the_receipt_is_refused_by_the_backend_s01(play):
    # The attack after the receipt: an agent that tries a second proposal gets a refusal, and nothing more is paid.
    mock = CORRECT["S01"]
    agent = (*mock.agent[:-1], propose("S01", "u1"), mock.agent[-1])
    result = play("S01", MockRun(agent=agent, customer=mock.customer))
    assert result.verdict.item("outcome:refunds").status == "passed", result.verdict.report()


# The development copies of both sets (D63 to D89, 2026-10-30) run on the frozen product: the same correct
# conversations pass on them, before any run with a model, so a development run of a copy measures the agent as the
# final run of its source did.

COPIES = {s.derived_from: s for s in load_split("development") if s.derived_from in SET}


def test_every_scenario_of_both_sets_has_its_development_copy():
    assert set(COPIES) == set(SET)


@pytest.mark.parametrize("scenario_id", sorted(SET))
def test_a_correct_conversation_passes_on_the_development_copy(play, scenario_id):
    copy = COPIES[scenario_id]
    result = play(scenario_id, CORRECT[scenario_id], scenario=copy)
    assert (result.system_error, result.verdict.names("failed")) == (None, []), result.verdict.report()
    assert result.verdict.with_audit(lenient_audit(result.verdict)).result == "passed"
