"""The customer side of a run: a script in mock mode, a model in a live run (plan section 9).

Both say the scenario's opening message first. After that, next_line() is asked once per answer of the agent and
returns the customer's next message, or None when the customer has nothing more to say.

The simulated customer is a model that sees only simulator_view(): the goal, the facts and how to behave, never the
fixture, the expectations or the staff decision. From its side of the conversation the agent is the other party, so
the agent's words reach it as the incoming messages and its own earlier lines as its answers. It ends the
conversation by replying [END]. Its errors are reported as the simulator's, apart from the agent's (plan section 11).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Protocol

from refund_agent.agent.model import ModelAdapter, ModelError
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import Scenario, simulator_view

SIMULATOR_INSTRUCTIONS = REPO_ROOT / "prompts" / "customer-simulator-v1.md"
END = "[END]"


class SimulatorError(Exception):
    """The simulated customer's model failed: a failure of the evaluation, never of the agent."""


class Customer(Protocol):
    def opening(self) -> str: ...

    def next_line(self, transcript: Sequence[tuple[str, str]]) -> str | None:
        """transcript: (author, text) of everything the customer and the agent said so far, in order."""
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

    def opening(self) -> str:
        return self.scenario.customer.opening_message

    def next_line(self, transcript: Sequence[tuple[str, str]]) -> str | None:
        if self.said >= self.max_lines:
            return None
        # Seen from the customer's side: the agent is the one writing in, and the customer's own lines are answers.
        messages = [
            {"role": "customer", "text": text}
            if author == "agent"
            else {"role": "agent", "text": text, "tool_calls": [], "continuation": []}
            for author, text in transcript
        ]
        try:
            text = self.model.respond(self.instructions, messages, []).text.strip()
        except ModelError as error:
            raise SimulatorError(f"{error.kind}: {error.detail}") from error
        if not text or END in text:
            return None
        self.said += 1
        return text
