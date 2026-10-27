"""The customer side of a run, without a database: the scripted customer and the simulated one, with a fake model."""

import pytest

from refund_agent.agent.model import ModelError, ModelTurn
from refund_agent.evaluation.customers import (
    ScriptedCustomer,
    SimulatedCustomer,
    SimulatorError,
    simulator_instructions,
)
from refund_agent.scenarios import format_brl, load_split

SCENARIOS = {s.id: s for s in load_split("development")}


class FakeModel:
    name = "fake"

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def respond(self, instructions, messages, tools):
        self.requests.append({"instructions": instructions, "messages": messages, "tools": tools})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ModelTurn(text=answer)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_the_simulated_customer_knows_its_goal_but_never_the_expected_answer(scenario_id):
    scenario = SCENARIOS[scenario_id]
    instructions = simulator_instructions(scenario)
    assert scenario.customer.goal in instructions
    for fact in scenario.customer.facts:
        assert fact.text in instructions
    expected = scenario.expected
    hidden = [*expected.refunded_units, *expected.cites, *expected.communication, *expected.forbidden]
    hidden += [unit.id for order in scenario.fixture.orders for unit in order.units]
    if expected.refund_amount_minor:
        hidden += [format_brl(expected.refund_amount_minor), str(expected.refund_amount_minor)]
    hidden += [scenario.staff.note] if scenario.staff.note else []
    assert [secret for secret in hidden if secret in instructions] == []


def test_a_fact_to_keep_until_asked_says_so():
    instructions = simulator_instructions(SCENARIOS["D09"])
    assert "You want the refund for the size L shirt. Say this only if you are asked about it." in instructions


def test_the_simulated_customer_sees_the_agent_as_the_other_party():
    model = FakeModel("The size L one.")
    customer = SimulatedCustomer(SCENARIOS["D09"], model)
    transcript = [("customer", customer.opening()), ("agent", "Which one do you mean, size M or size L?")]
    assert customer.next_line(transcript) == "The size L one."
    request = model.requests[0]
    assert [m["role"] for m in request["messages"]] == ["agent", "customer"]  # its own opening, then the agent
    assert request["messages"][1]["text"] == "Which one do you mean, size M or size L?"
    assert request["tools"] == []  # the customer has no buttons


def test_the_simulated_customer_ends_the_conversation():
    customer = SimulatedCustomer(SCENARIOS["D01"], FakeModel("Thanks!", "[END]"))
    assert customer.next_line([("customer", "Hi"), ("agent", "Done.")]) == "Thanks!"
    assert (
        customer.next_line([("customer", "Hi"), ("agent", "Done."), ("customer", "Thanks!"), ("agent", "Bye")]) is None
    )
    limited = SimulatedCustomer(SCENARIOS["D01"], FakeModel("one", "two"), max_lines=1)
    assert limited.next_line([]) == "one" and limited.next_line([]) is None  # the bound on its messages


def test_a_failure_of_the_simulator_is_reported_as_its_own():
    customer = SimulatedCustomer(SCENARIOS["D01"], FakeModel(ModelError("rate_limit", retryable=True, detail="slow")))
    with pytest.raises(SimulatorError, match="rate_limit"):
        customer.next_line([("customer", "Hi"), ("agent", "Hello")])


def test_the_scripted_customer_says_its_lines_in_order():
    customer = ScriptedCustomer(SCENARIOS["D02"], ["Add the plate, please."])
    assert customer.opening() == SCENARIOS["D02"].customer.opening_message
    assert customer.next_line([]) == "Add the plate, please." and customer.next_line([]) is None


# A question or an offer waiting for the customer (final evaluation of v1.1, H41 try 3 of A and C): the agent offered a
# staff member for the shipping charge, the role said to accept, and the simulated customer replied [END]. In all
# saved runs 23 of 1,604 conversations ended with an agent question unanswered. The instructions now ask for an answer
# first, and an end in front of a question is asked once more, with a reminder.

OFFER = "I can't add shipping to the item. Would you like a staff member to review the shipping charge?"


def test_the_instructions_ask_for_an_answer_before_the_end():
    instructions = simulator_instructions(SCENARIOS["D01"])
    assert "first answer it" in instructions and "nothing in the assistant's last message waits" in instructions


def test_an_end_in_front_of_a_question_is_asked_once_more():
    model = FakeModel("[END]", "Yes, please.")
    customer = SimulatedCustomer(SCENARIOS["D40"], model)
    assert customer.next_line([("customer", "Hi"), ("agent", OFFER)]) == "Yes, please."
    first, again = model.requests
    assert again["messages"] == first["messages"]
    assert again["instructions"].startswith(first["instructions"])
    assert "asks you something" in again["instructions"][len(first["instructions"]) :]
    assert customer.reminders == ["answered"]  # counted apart in the report


def test_an_end_that_holds_after_the_reminder_ends_the_conversation():
    model = FakeModel("[END]", "[END]")
    customer = SimulatedCustomer(SCENARIOS["D40"], model)
    assert customer.next_line([("customer", "Hi"), ("agent", OFFER)]) is None
    assert len(model.requests) == 2  # asked once more, never in a loop
    assert customer.reminders == ["ended"]  # flagged for the reader


def test_an_end_with_no_question_in_front_of_it_is_taken_at_once():
    model = FakeModel("[END]")
    transcript = [("customer", "Hi"), ("agent", "Your refund is paid; the receipt is R-00000001.")]
    assert SimulatedCustomer(SCENARIOS["D01"], model).next_line(transcript) is None
    assert len(model.requests) == 1


# A question followed by a fact line (review of 2026-10-27): the runner passes the fact line said after an answer as a
# message of its own, so the question was no longer the last entry and no reminder came. The check reads the agent's
# last answer, past any fact line after it; an earlier question that later events settled is not asked again (in the
# saved runs, 6 conversations ended so, such as D17: "which shears?", then the refund paid).

FACT = "Only orders recorded as delivered can be refunded through this process (refund-policy/v2/eligible-orders)."


def test_a_question_followed_by_a_fact_line_is_still_a_question():
    model = FakeModel("[END]", "Yes, please.")
    customer = SimulatedCustomer(SCENARIOS["D40"], model)
    assert customer.next_line([("customer", "Hi"), ("agent", OFFER), ("fact_line", FACT)]) == "Yes, please."
    assert len(model.requests) == 2
    # The fact line reaches the simulated customer as the shop's message, as before.
    assert [m["role"] for m in model.requests[0]["messages"]] == ["agent", "customer", "customer"]


def test_a_question_that_later_events_settled_is_not_asked_again():
    model = FakeModel("[END]")
    transcript = [("customer", "Hi"), ("agent", "Which shears do you mean?"), ("agent", "Your refund is paid: R-1.")]
    assert SimulatedCustomer(SCENARIOS["D17"], model).next_line(transcript) is None
    assert len(model.requests) == 1


def test_the_runner_marks_a_fact_line_for_the_customer_side():
    from refund_agent.evaluation.runner import _transcript

    messages = [
        {"role": "customer", "text": "Hi"},
        {"role": "agent", "text": OFFER, "tool_calls": [], "continuation": []},
        {"role": "tool", "call_id": "c1", "name": "list_my_orders", "content": "{}"},
        {"role": "agent", "text": FACT, "fact_line": True},
        {"role": "event", "text": "A staff member approved it.", "notice_id": "n1"},
    ]
    assert _transcript(messages) == [("customer", "Hi"), ("agent", OFFER), ("fact_line", FACT)]


def test_the_reminders_are_saved_with_the_result(tmp_path):
    import json

    from refund_agent.evaluation.evaluator import Verdict
    from refund_agent.evaluation.runner import RunResult
    from refund_agent.evaluation.trials import save_result

    result = RunResult("D40", "A", Verdict("D40", ()), [], 0, None, simulator_reminders=["ended"])
    save_result(tmp_path, result, 1, {})
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["simulator_reminders"] == ["ended"]
