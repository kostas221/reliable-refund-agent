"""The runner: plays one scenario from start to finish and has the evaluator judge it (plan sections 9 and 10).

The agent answers through the conversation graph, with any model adapter: the scripted one in mock mode, a real one
in a paid run. Around it the runner plays the people, by the scenario's own rules:

- the customer (a script in mock mode, a model in a live run: refund_agent/evaluation/customers.py) says the opening
  message, then one line after each answer of the agent, until it has nothing more to say;
- the customer's confirm button (the test actor) is pressed only on a proposal with exactly the units and amount the
  scenario's customer confirms, and every other proposal waiting for the customer is declined;
- the scripted staff member applies the scenario's decision to every proposal that reaches the queue, and the agent
  is told, as the staff console does.

The business clock moves one minute per step, so the order of events is plain. A model error or a loop is a failure
of the system, and a failure of the simulated customer is the evaluation's: each is kept in the result, apart, and
the evaluator still judges what the database holds (plan section 11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import Engine, text

from refund_agent.agent.graph import Agent, AgentLoopError
from refund_agent.agent.model import ModelAdapter, ModelError
from refund_agent.evaluation.customers import Customer, SimulatorError
from refund_agent.evaluation.evaluator import Verdict, capture_baseline, evaluate
from refund_agent.fixtures import seed
from refund_agent.policy import Policy
from refund_agent.refunds import Actor, Configuration, confirm, decide, open_conversation
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
    error = simulator_error = None
    try:
        clock.tick()
        agent.receive(conversation, customer.opening())
        for _ in range(max_rounds):
            if _people_act(scenario, app, agent, conversation, clock, policy):
                continue
            line = customer.next_line(_transcript(agent.messages(conversation)))
            if line is None:
                break
            clock.tick()
            agent.receive(conversation, line)
    except (ModelError, AgentLoopError) as failure:
        error = f"{type(failure).__name__}: {failure}"
    except SimulatorError as failure:
        simulator_error = str(failure)
    usage = agent.usage(conversation)
    verdict = evaluate(scenario, app, baseline)
    return RunResult(
        scenario.id, configuration, verdict, agent.messages(conversation), len(usage), error, simulator_error
    )


def _transcript(messages: list[dict]) -> list[tuple[str, str]]:
    return [(m["role"], m["text"]) for m in messages if m["role"] in ("customer", "agent") and m.get("text")]


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


def _people_act(scenario: Scenario, app: Engine, agent: Agent, conversation: str, clock: Clock, policy: Policy) -> bool:
    """The customer's button and the staff decision. True when the agent was told something and answered."""
    customer = Actor("customer", scenario.customer.id)
    for proposal, units, amount in _proposals(app, conversation, "awaiting_customer_confirmation"):
        accepts = customer_confirms(scenario.customer, units, amount)
        confirm(app, customer, proposal, "confirmed" if accepts else "declined", clock.tick(), policy)
    if scenario.staff.decision == "none":
        return False
    staff = Actor("staff", scenario.fixture.staff[0].id)
    decision = "approved" if scenario.staff.decision == "approve" else "rejected"
    for proposal, _, _ in _proposals(app, conversation, "awaiting_staff_approval"):
        decide(app, staff, proposal, decision, clock.tick(), policy)
        clock.tick()
        agent.notify(conversation, f"Request {proposal} was {decision} by a staff member.")
        return True
    return False
