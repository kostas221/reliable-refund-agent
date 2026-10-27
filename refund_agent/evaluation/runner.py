"""The runner: plays one scenario from start to finish and has the evaluator judge it (plan sections 9 and 10).

The agent answers through the conversation graph, with any model adapter: the scripted one in mock mode, a real one
in a paid run. Around it the runner plays the people, by the scenario's own rules:

- the customer (a script in mock mode, a model in a live run: refund_agent/evaluation/customers.py) says the opening
  message, then one line after each answer of the agent, until it has nothing more to say;
- the customer's buttons (the test actor): confirm only on a proposal with exactly the units and amount the scenario's
  customer confirms, then keep it or cancel it before the staff decision; any other proposal waiting for the
  customer is declined, or left open while the customer asks for a change in the chat (`customer.cards`); the agent
  is told of a cancellation or a decline before the customer writes again;
- the scripted staff member applies the scenario's decision to every proposal that reaches the queue, and the agent
  is told, as the staff console does.

The business clock moves one minute per step, so the order of events is plain. A model error or a loop is a failure
of the system, and a failure of the simulated customer is the evaluation's: each is kept in the result, apart, and
the evaluator still judges what the database holds (plan section 11). A budget stop ends the conversation the same
way: what was done before it is judged and kept (outside review of 2026-10-15).

Besides the verdict, a result keeps what the final report needs and the database will not hold once it is dropped
(plan section 11): every attempt the backend refused, the origin of every handoff, and how long each run of the
agent took (one per customer message or notice: the automated part, without the people's waiting).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import Engine, text

from refund_agent.agent import notices
from refund_agent.agent.costs import BudgetExceeded
from refund_agent.agent.graph import Agent, AgentLoopError
from refund_agent.agent.model import ModelAdapter, ModelError
from refund_agent.evaluation.customers import Customer, SimulatorError
from refund_agent.evaluation.evaluator import Item, Verdict, capture_baseline, evaluate
from refund_agent.fixtures import seed
from refund_agent.policy import Policy
from refund_agent.refunds import Actor, Configuration, cancel, confirm, decide, open_conversation
from refund_agent.scenarios import Scenario, customer_confirms


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def tick(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


@dataclass(frozen=True)
class RunResult:
    scenario: str
    configuration: Configuration
    verdict: Verdict
    messages: list[dict]
    model_requests: int
    system_error: str | None  # the agent's model error or loop: a failure of the system, never hidden
    simulator_error: str | None = None  # the simulated customer failed: the run is not a valid test of the agent
    stopped_by_budget: str | None = None  # the budget stopped the run before a request: not a valid test either
    # How the conversation ended: customer_ended (by the customer), round_limit or customer_limit (cut off by the
    # runner's bound, never a normal end: review of 2026-10-19, R5), agent_error, simulator_error or budget.
    ended: str = "customer_ended"
    refusals: list[dict] = field(default_factory=list)  # attempts the backend refused: event, check, actor type
    handoff_origins: list[str] = field(default_factory=list)  # customer, agent or staff, in order
    agent_seconds: list[float] = field(default_factory=list)  # each run of the agent, wall-clock
    # Each reminder the simulated customer got to answer a question before ending: "answered" or "ended".
    simulator_reminders: list[str] = field(default_factory=list)


def run_scenario(
    scenario: Scenario,
    customer: Customer,
    model: ModelAdapter,
    *,
    owner: Engine,
    app: Engine,
    checkpointer: BaseCheckpointSaver,
    policy: Policy,
    configuration: Configuration = "A",
    max_rounds: int = 20,
) -> RunResult:
    """owner and app: the two roles on a fresh, migrated database; the scenario's fixture is loaded here."""
    seed(owner, scenario, policy)
    baseline = capture_baseline(app)
    clock = Clock(scenario.now)
    agent = Agent(app, policy, model, checkpointer, clock, configuration=configuration)
    conversation = open_conversation(app, Actor("customer", scenario.customer.id), clock())
    error = simulator_error = stopped = None
    ended = "round_limit"  # unless the loop ends otherwise
    seconds: list[float] = []

    def timed(run: Callable[[], object]) -> object:
        started = time.perf_counter()
        try:
            return run()
        finally:
            seconds.append(round(time.perf_counter() - started, 3))

    try:
        clock.tick()
        timed(lambda: agent.receive(conversation, customer.opening()))
        for _ in range(max_rounds):
            if _people_act(scenario, app, agent, conversation, clock, policy, timed):
                continue
            line = customer.next_line(_transcript(agent.messages(conversation)))
            if line is None:
                ended = "customer_limit" if getattr(customer, "cut_off", False) else "customer_ended"
                break
            clock.tick()
            timed(lambda line=line: agent.receive(conversation, line))
    except (ModelError, AgentLoopError) as failure:
        error, ended = f"{type(failure).__name__}: {failure}", "agent_error"
    except SimulatorError as failure:
        simulator_error, ended = str(failure), "simulator_error"
    except BudgetExceeded as stop:
        stopped, ended = str(stop), "budget"
    usage = agent.usage(conversation)
    messages = agent.messages(conversation)
    verdict = evaluate(scenario, app, baseline, received=tool_texts(messages))
    if ended in CUT_OFF:
        # The outcome may look complete, but the customer did not end it: a person decides whether it was resolved.
        why = f"cut off by the {CUT_OFF[ended]} before the conversation ended; the dialogue audit decides"
        verdict = Verdict(verdict.scenario, (*verdict.items, Item("conversation:cut_off", "pending", why)))
    refusals, origins = _evidence(app, baseline.last_audit_event, conversation)
    return RunResult(
        scenario.id,
        configuration,
        verdict,
        messages,
        len(usage),
        error,
        simulator_error,
        stopped,
        ended,
        refusals,
        origins,
        seconds,
        list(getattr(customer, "reminders", [])),
    )


def _evidence(app: Engine, after_event: int, conversation: str) -> tuple[list[dict], list[str]]:
    """The attempts refused during the run, and the origins of its handoffs."""
    with app.connect() as conn:
        refused = conn.execute(
            text(
                "SELECT event, reason, actor_type FROM audit_events WHERE id > :after AND outcome = 'rejected' "
                "ORDER BY id"
            ),
            {"after": after_event},
        ).mappings()
        refusals = [{"event": r["event"], "check": r["reason"], "actor": r["actor_type"]} for r in refused]
        origins = conn.execute(
            text("SELECT origin FROM handoffs WHERE conversation_id = :c ORDER BY created_at, id"), {"c": conversation}
        ).scalars()
        return refusals, list(origins)


CUT_OFF = {"round_limit": "runner's limit of rounds", "customer_limit": "simulated customer's limit of messages"}


def tool_texts(messages: list[dict]) -> list[str]:
    """Every text the agent received in a tool result, decoded from the JSON it was sent as: what the evaluator
    searches for an attack planted in the shop's data."""

    def texts(value: object) -> Iterator[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for inner in value.values():
                yield from texts(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from texts(inner)

    return [t for m in messages if m["role"] == "tool" for t in texts(json.loads(m["content"]))]


def _transcript(messages: list[dict]) -> list[tuple[str, str]]:
    """What the customer side reads: each text said, with a fact line said from the records marked as such, so
    a question in the answer before it still counts as the last thing asked (review of 2026-10-27)."""
    return [
        ("fact_line" if m.get("fact_line") else m["role"], m["text"])
        for m in messages
        if m["role"] in ("customer", "agent") and m.get("text")
    ]


def _proposals(app: Engine, conversation: str, status: str) -> list[tuple[str, list[str], int]]:
    with app.connect() as conn:
        found = conn.execute(
            text(
                "SELECT p.id, p.amount_minor, array_agg(pu.order_unit_id ORDER BY pu.order_unit_id) AS units "
                "FROM proposals p JOIN proposal_units pu ON pu.proposal_id = p.id "
                "WHERE p.conversation_id = :c AND p.status = :s GROUP BY p.id ORDER BY min(p.created_at), p.id"
            ),
            {"c": conversation, "s": status},
        ).mappings()
        return [(row["id"], list(row["units"]), row["amount_minor"]) for row in found]


def _people_act(
    scenario: Scenario,
    app: Engine,
    agent: Agent,
    conversation: str,
    clock: Clock,
    policy: Policy,
    timed: Callable[[Callable[[], object]], object] = lambda run: run(),
) -> bool:
    """The customer's button and the staff decision. True when the agent was told something and answered."""
    customer, cards = Actor("customer", scenario.customer.id), scenario.customer.cards
    pressed = False  # cancel or decline
    for proposal, units, amount in _proposals(app, conversation, "awaiting_customer_confirmation"):
        if customer_confirms(scenario.customer, units, amount):
            confirm(app, customer, proposal, "confirmed", clock.tick(), policy)
            if cards.after_confirming == "cancel":
                cancel(app, customer, proposal, clock.tick(), policy)
                pressed = True
        elif cards.other == "decline":
            confirm(app, customer, proposal, "declined", clock.tick(), policy)
            pressed = True
        # wait: the card stays open while the customer, in the chat, asks for a change
    # A cancellation or a decline stored its notice (review of the model comparison, 2026-10-24; final evaluation of
    # v1.1, 2026-10-26): it is delivered before the customer writes again, through the same delivery as a staff
    # decision, and starts no run of the agent, which reads it at the customer's next message (confirmation run of
    # 2026-10-24). No run, so no time is counted.
    if pressed:
        notices.deliver_pending(app, agent, clock, conversation)
    if scenario.staff.decision == "none":
        return False
    staff = Actor("staff", scenario.fixture.staff[0].id)
    decision = "approved" if scenario.staff.decision == "approve" else "rejected"
    reason = scenario.staff.note if decision == "rejected" else None
    for proposal, _, _ in _proposals(app, conversation, "awaiting_staff_approval"):
        decide(app, staff, proposal, decision, clock.tick(), policy, reason=reason)
        clock.tick()
        # The product's path: the decision stored its notice, and the agent is told through the same delivery.
        return timed(lambda: notices.deliver_pending(app, agent, clock, conversation)) > 0
    return False
