"""The customer side of a run: a script in mock mode, a model in a live run (plan section 9).

Both say the scenario's opening message first. After that, next_line() is asked once per answer of the agent and
returns the customer's next message, or None when the customer has nothing more to say.

The simulated customer is a model that sees only simulator_view(): the goal, the facts and how to behave, never the
fixture, the expectations or the staff decision. From its side of the conversation the agent is the other party, so
the agent's words reach it as the incoming messages and its own earlier lines as its answers. It ends the
conversation by replying [END]; an end in front of the agent's question or offer is asked once more, with a
reminder to answer it first. Its errors are reported as the simulator's, apart from the agent's (plan section 11).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Protocol

from refund_agent.agent.model import ModelAdapter, ModelError
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import Scenario, simulator_view

SIMULATOR_INSTRUCTIONS = REPO_ROOT / "prompts" / "customer-simulator-v2.md"
END = "[END]"
# Said once more when the customer ends in front of a question (final evaluation of v1.1, H41 try 3 of A and C: the
# role said to accept the offered staff member, and the simulated customer ended instead).
REMINDER = (
    "\n\nThe assistant's last message asks you something or offers you something. Answer it as your goal and behaviour "
    "say before you end; reply [END] only if nothing in it waits for your answer."
)


def _asks(transcript: Sequence[tuple[str, str]]) -> bool:
    """Whether the agent's last answer, past any fact line said after it, has a question mark. An earlier answer's
    question that later events settled does not count (review of 2026-10-27: D17 asked which shears, then paid)."""
    for author, text in reversed(transcript):
        if author != "fact_line":
            return author == "agent" and "?" in text
    return False


class SimulatorError(Exception):
    """The simulated customer's model failed: a failure of the evaluation, never of the agent."""


class Customer(Protocol):
    def opening(self) -> str: ...

    def next_line(self, transcript: Sequence[tuple[str, str]]) -> str | None:
        """transcript: (author, text) of everything the customer and the agent said so far, in order; author is
        "customer", "agent", or "fact_line" for the line said from the records after an agent's answer."""
        ...


class ScriptedCustomer:
    def __init__(self, scenario: Scenario, lines: Sequence[str]) -> None:
        self.scenario, self.lines = scenario, deque(lines)

    def opening(self) -> str:
        return self.scenario.customer.opening_message

    def next_line(self, transcript: Sequence[tuple[str, str]]) -> str | None:
        return self.lines.popleft() if self.lines else None


def simulator_instructions(scenario: Scenario) -> str:
    view = simulator_view(scenario)
    facts = [
        f"- {fact['text']}" + (" Say this only if you are asked about it." if fact["reveal"] == "when_asked" else "")
        for fact in view["facts"]
    ]
    behaviour = [f"- {line}" for line in view["behaviour"]]
    template = SIMULATOR_INSTRUCTIONS.read_text(encoding="utf-8")
    return template.format(
        goal=view["goal"],
        facts="\n".join(facts) or "- Nothing beyond your goal.",
        behaviour="\n".join(behaviour) or "- Nothing special.",
    )


class SimulatedCustomer:
    def __init__(self, scenario: Scenario, model: ModelAdapter, max_lines: int = 8) -> None:
        """max_lines: the customer's messages after the opening, a bound on the conversation and its cost."""
        self.scenario, self.model, self.max_lines = scenario, model, max_lines
        self.instructions = simulator_instructions(scenario)
        self.said = 0
        self.cut_off = False  # True once max_lines stopped it: not an end the customer chose
        # Each reminder, in order: "answered" or "ended" (the customer ended anyway), counted apart in the report and
        # flagged for the reader, since the simulator changed the conversation's course there (review of 2026-10-27).
        self.reminders: list[str] = []

    def opening(self) -> str:
        return self.scenario.customer.opening_message

    def next_line(self, transcript: Sequence[tuple[str, str]]) -> str | None:
        if self.said >= self.max_lines:
            self.cut_off = True
            return None
        # Seen from the customer's side: the shop is the one writing in, and the customer's own lines are answers.
        messages = [
            {"role": "agent", "text": text, "tool_calls": [], "continuation": []}
            if author == "customer"
            else {"role": "customer", "text": text}
            for author, text in transcript
        ]
        text = self._respond(self.instructions, messages)
        if (not text or END in text) and _asks(transcript):
            text = self._respond(self.instructions + REMINDER, messages)  # once, never in a loop
            self.reminders.append("ended" if not text or END in text else "answered")
        if not text or END in text:
            return None
        self.said += 1
        return text

    def _respond(self, instructions: str, messages: list[dict]) -> str:
        try:
            return self.model.respond(instructions, messages, []).text.strip()
        except ModelError as error:
            raise SimulatorError(f"{error.kind}: {error.detail}") from error
