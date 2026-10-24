"""Diagnostics of a run: measures that explain failures without changing the strict score (plan change log,
2026-10-20, v1.1 step 0). They count from the saved conversations what the analysis of v1 counted by hand
(docs/final/results.md, "Why A failed"), so each step of v1.1 can be compared with v1 on the same terms.

- Citations: for every citation a scenario requires, whether the section had been shown to the agent and whether
  the agent cited it. A section is shown when a tool result names it (a refusal's citations, a policy lookup), or
  when the agent's instructions contain its full text. An ID quoted as an example, without the text, is not shown.
- Handoffs the scenario forbids, by who began them; required handoffs that are missing or came from the wrong side.
- Proposals after a receipt: a new proposal in a conversation whose refund was already paid.
- Proposal denials: an agent message that says no proposal was made, after this conversation made an eligible one
  (plan change log, 2026-10-22). A pattern over the agent's words: it finds the claims of step 2's D17 and is read
  in the audit; it changes no verdict.
- Checks of 2026-10-23, where they acted: calls held because the agent's answer asked the customer a question, proposals
  refused because the customer's words do not yet say which look-alike they mean (and conversations where that
  happened twice or more, a sign of a loop), and handoffs refused because a yes answered no offer the check could
  read, apart from other refusals of a handoff. They show whether each change was exercised, not whether it helped.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from refund_agent.policy import Policy
from refund_agent.refunds import YES_WITHOUT_OFFER
from refund_agent.scenarios import Scenario

CITATION = re.compile(r"refund-policy/v[0-9]+/[a-z-]+")
DENIES_PROPOSAL = re.compile(
    r"\b(?:have not|haven['\u2019]t|did not|didn['\u2019]t)\b[^.?!]{0,30}?"
    r"\b(?:proposed|(?:created|made) (?:a|any) proposal)",
    re.IGNORECASE,
)


def instructions_of(try_folder: Path) -> str:
    """The instructions of the agent's first request in this try, as it received them; empty if none was logged."""
    log = try_folder / "agent-requests.jsonl"
    if not log.exists():
        return ""
    first = log.read_text(encoding="utf-8").split("\n", 1)[0]
    return json.loads(first).get("instructions", "") if first else ""


def shown_sections(messages: list[dict], instructions: str, policy: Policy) -> set[str]:
    shown = {policy.citation(s.id) for s in policy.sections if policy.rendered_text(s.id).strip() in instructions}
    for message in messages:
        if message["role"] == "tool":
            shown |= set(CITATION.findall(message["content"]))
    return shown


def proposals_after_receipt(messages: list[dict]) -> int:
    paid, count = False, 0
    for message in messages:
        if message["role"] == "tool" and message["name"] == "execute_refund":
            paid = paid or bool(json.loads(message["content"]).get("receipt"))
        elif paid:
            count += sum(call["name"] == "propose_refund" for call in message.get("tool_calls") or [])
    return count


def proposal_denials(messages: list[dict]) -> int:
    proposed, count = False, 0
    for message in messages:
        if message["role"] == "tool" and message["name"] == "propose_refund":
            proposed = proposed or json.loads(message["content"]).get("outcome") == "eligible"
        elif message["role"] == "agent" and proposed and DENIES_PROPOSAL.search(message.get("text") or ""):
            count += 1
    return count


CHECKS_ACTED = (
    "calls held after a question",
    "proposals refused, the customer's words do not say which",
    "handoffs refused, a yes to no offer in view",
    "handoffs refused, other reasons",
)
REPEATED_SELECTION = "conversations with the selection refused twice or more"


def checks_acted(messages: list[dict]) -> Counter:
    counted = Counter()
    for message in messages:
        if message["role"] != "tool":
            continue
        result = json.loads(message["content"])
        if result.get("not_run") == "question_to_customer":
            counted[CHECKS_ACTED[0]] += 1
        elif result.get("refused") == "units_named":
            counted[CHECKS_ACTED[1]] += 1
        elif result.get("refused") == "handoff_reason":
            yes = result.get("explanation", "").startswith(YES_WITHOUT_OFFER)
            counted[CHECKS_ACTED[2] if yes else CHECKS_ACTED[3]] += 1
    return counted


def of_try(
    saved: dict, failed: set[str], items: dict[str, str], scenario: Scenario, instructions: str, policy: Policy
) -> dict:
    """One conversation. failed: the item names that failed; items: every item name and its status."""
    shown = shown_sections(saved.get("messages", []), instructions, policy)
    # What the model wrote, without the graph's fact lines (agent/facts.py), so their citations are counted apart.
    model_said = " ".join(
        m.get("text") or "" for m in saved.get("messages", []) if m.get("role") == "agent" and not m.get("fact_line")
    )
    citations = Counter()
    for name, status in items.items():
        if name.startswith("cites:"):
            citation = name.split(":", 1)[1]
            seen = "shown" if citation in shown else "never shown"
            cited = "not cited"
            if status == "passed":
                cited = "cited" if citation in model_said else "cited only by the fact line"
            citations[f"{seen}, {cited}"] += 1
    handoffs = Counter()
    if "handoff" in failed:
        origins = saved.get("handoff_origins", [])
        if scenario.expected.handoff == "forbidden":
            handoffs.update(f"forbidden, begun by the {origin}" for origin in origins)
        else:
            handoffs["required, " + ("missing" if not origins else "from the wrong side")] += 1
    return {
        "citations": citations,
        "handoffs": handoffs,
        "proposals_after_receipt": proposals_after_receipt(saved.get("messages", [])),
        "proposal_denials": proposal_denials(saved.get("messages", [])),
        "checks_acted": checks_acted(saved.get("messages", [])),
    }


def summarize(per_try: list[dict]) -> dict:
    total = {"citations": Counter(), "handoffs": Counter(), "proposals_after_receipt": 0, "proposal_denials": 0}
    acted = Counter({name: 0 for name in (*CHECKS_ACTED, REPEATED_SELECTION)})
    for d in per_try:
        acted.update(d.get("checks_acted", {}))
        acted[REPEATED_SELECTION] += d.get("checks_acted", {}).get(CHECKS_ACTED[1], 0) >= 2
        total["citations"].update(d["citations"])
        total["handoffs"].update(d["handoffs"])
        total["proposals_after_receipt"] += d["proposals_after_receipt"]
        total["proposal_denials"] += d.get("proposal_denials", 0)
    return {
        "citations": dict(sorted(total["citations"].items())),
        "handoffs": dict(sorted(total["handoffs"].items())),
        "proposals_after_receipt": total["proposals_after_receipt"],
        "proposal_denials": total["proposal_denials"],
        "checks_acted": dict(acted),
    }
