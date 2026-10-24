"""Replay the checks of 2026-10-23 on saved runs: what they would have decided at every recorded step, with no model
(plan change log, 2026-10-23). It runs the production functions on what the logs hold, so it shows what a check
decides, never what the model would have said after a different tool result; only a new run shows that.

- Selection (refund_agent/selection.py): every recorded propose_refund call, with the customer's look-alikes as the
  scenario's fixture gives them (units paid in the conversation leave the group) and the messages said before it.
- Question brake (refund_agent/agent/graph.py): every agent answer with text and tool calls, and whether the text
  asks the customer something.
- Request for a person (refunds.request_for_person): every recorded customer_asked attempt, against what the backend
  answered at the time.
- Request to refund shipping (refunds.request_for_shipping_refund, review after the selection check; a yes to the
  agent's offer since the review of the model comparison): every recorded shipping_refund attempt, against what the
  backend answered at the time.
- Fact line (refund_agent/agent/facts.py, review of the model comparison): every agent answer with text and no calls,
  and the line the graph would now say after it.

Run: uv run python -m refund_agent.evaluation.replay runs/pilot-20261022T165428Z-gpt-6-luna-none [more runs]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from refund_agent.agent.facts import fact_line
from refund_agent.policy import Policy
from refund_agent.refunds import request_for_person, request_for_shipping_refund
from refund_agent.scenarios import Scenario, load_split, policy_for
from refund_agent.selection import Kind, asks_customer, look_alikes_unnamed


@dataclass
class Replayed:
    proposals: int = 0
    refused: list[str] = field(default_factory=list)  # "D31 try1 call 1: units ..." for each refused proposal
    answers_with_calls: int = 0
    held: list[str] = field(default_factory=list)
    agent_answers: int = 0
    handoffs: int = 0
    changed: list[str] = field(default_factory=list)  # customer_asked attempts the rule now decides differently
    shipping: int = 0
    shipping_changed: list[str] = field(default_factory=list)  # shipping_refund attempts now decided differently
    fact_lines: list[str] = field(default_factory=list)  # "<where>: <line>" for each answer that would get one


def kinds_of(scenario: Scenario, paid: set[str]) -> list[Kind]:
    found: dict[tuple[str, str], Kind] = {}
    refunded = {unit for refund in scenario.fixture.past_refunds for unit in refund.units} | paid
    for order in scenario.fixture.orders:
        if order.customer != scenario.customer.id:
            continue
        for unit in order.units:
            if unit.id in refunded:
                continue
            key = (order.id, unit.product)
            kind = found.get(key) or Kind(
                order.id,
                unit.product,
                order.purchased_at.date(),
                order.delivered_at.date() if order.delivered_at else None,
                (),
            )
            found[key] = Kind(kind.order_id, kind.product, kind.placed, kind.delivered, (*kind.unit_ids, unit.id))
    return list(found.values())


def replay_try(saved: dict, scenario: Scenario, where: str, into: Replayed, policy: Policy) -> None:
    said: list[tuple[str, str]] = []  # (author, text) of customer and agent, as the messages table holds them
    paid: set[str] = set()
    history: list[dict] = []  # the messages before the one at hand, as the graph keeps them
    for message in saved.get("messages", []):
        history.append(message)
        role = message["role"]
        if role == "tool":
            result = json.loads(message["content"])
            paid |= {unit["unit_id"] for unit in (result.get("receipt") or {}).get("units", [])}
            continue
        if role == "agent":
            into.agent_answers += 1
            calls = message.get("tool_calls") or []
            if message.get("text") and calls:
                into.answers_with_calls += 1
                if asks_customer(message["text"]):
                    into.held.append(f"{where}: {', '.join(call['name'] for call in calls)}")
            if message.get("text") and not calls and not message.get("fact_line"):
                line = fact_line(history[:-1], message["text"], policy)
                if line:
                    into.fact_lines.append(f"{where}: {line}")
            if message.get("text"):  # stored before the answer's own calls run
                said.append(("agent", message["text"]))
            for call in calls:
                arguments = json.loads(call["arguments"] or "{}")
                if call["name"] == "propose_refund":
                    into.proposals += 1
                    group = look_alikes_unnamed(kinds_of(scenario, paid), arguments.get("unit_ids", []), said)
                    if group:
                        into.refused.append(f"{where} {call['call_id']}: {', '.join(arguments['unit_ids'])}")
                elif (
                    call["name"] == "request_handoff"
                    and arguments.get("reason_code") == "customer_asked"
                    and "customer_words" in arguments  # runs before the check of 2026-10-21 have nothing to compare
                ):
                    into.handoffs += 1
                    numbered = [(f"m{n}", author, text) for n, (author, text) in enumerate(said)]
                    now = request_for_person(numbered, arguments.get("customer_words", "")).message_id is not None
                    recorded = _recorded_answer(saved, call["call_id"])
                    if recorded is not None and now != recorded:
                        into.changed.append(
                            f"{where}: {'accepted' if now else 'refused'} {arguments['customer_words']!r}"
                        )
                elif call["name"] == "request_handoff" and arguments.get("reason_code") == "shipping_refund":
                    into.shipping += 1
                    numbered = [(f"m{n}", author, text) for n, (author, text) in enumerate(said)]
                    words = arguments.get("customer_words", "")
                    now = request_for_shipping_refund(numbered, words)[0] is not None
                    recorded = _recorded_answer(saved, call["call_id"])
                    if recorded is not None and now != recorded:
                        into.shipping_changed.append(f"{where}: {'accepted' if now else 'refused'} {words!r}")
        elif role == "customer" and message.get("text"):
            said.append(("customer", message["text"]))


def _recorded_answer(saved: dict, call_id: str) -> bool | None:
    """Whether the backend accepted this handoff call when it ran."""
    for message in saved.get("messages", []):
        if message["role"] == "tool" and message.get("call_id") == call_id:
            return bool(json.loads(message["content"]).get("ok"))
    return None


def replay(runs: list[Path]) -> Replayed:
    scenarios = {s.id: s for s in load_split("development")}
    policy = policy_for(scenarios.values())
    into = Replayed()
    for run in runs:
        for result in sorted(run.glob("D*/try*/result.json")):
            scenario = scenarios.get(result.parent.parent.name)
            if scenario is None:
                continue
            where = f"{run.name} {result.parent.parent.name} {result.parent.name}"
            replay_try(json.loads(result.read_text(encoding="utf-8")), scenario, where, into, policy)
    return into


def main(argv: list[str] | None = None) -> int:
    runs = [Path(arg) for arg in (argv if argv is not None else sys.argv[1:])]
    found = replay(runs)
    print(f"Selection: {len(found.refused)} of {found.proposals} proposal calls refused")
    for line in found.refused:
        print(f"  {line}")
    print(
        f"Question brake: {len(found.held)} of {found.answers_with_calls} answers with text and calls held, "
        f"of {found.agent_answers} answers"
    )
    for line in found.held:
        print(f"  {line}")
    print(f"Request for a person: {len(found.changed)} of {found.handoffs} customer_asked attempts decided differently")
    for line in found.changed:
        print(f"  {line}")
    print(
        f"Request to refund shipping: {len(found.shipping_changed)} of {found.shipping} shipping_refund attempts "
        "decided differently"
    )
    for line in found.shipping_changed:
        print(f"  {line}")
    print(f"Fact line: {len(found.fact_lines)} answers would get one")
    for line in found.fact_lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
