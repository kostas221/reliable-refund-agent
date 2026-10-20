"""Diagnostics of a run: measures that explain failures without changing the strict score (plan change log,
2026-10-20, v1.1 step 0). They count from the saved conversations what the analysis of v1 counted by hand
(docs/final/results.md, "Why A failed"), so each step of v1.1 can be compared with v1 on the same terms.

- Citations: for every citation a scenario requires, whether the section had been shown to the agent and whether
  the agent cited it. A section is shown when a tool result names it (a refusal's citations, a policy lookup), or
  when the agent's instructions contain its full text. An ID quoted as an example, without the text, is not shown.
- Handoffs the scenario forbids, by who began them; required handoffs that are missing or came from the wrong side.
- Proposals after a receipt: a new proposal in a conversation whose refund was already paid.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from refund_agent.policy import Policy
from refund_agent.scenarios import Scenario

CITATION = re.compile(r"refund-policy/v[0-9]+/[a-z-]+")


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


def of_try(
    saved: dict, failed: set[str], items: dict[str, str], scenario: Scenario, instructions: str, policy: Policy
) -> dict:
    """One conversation. failed: the item names that failed; items: every item name and its status."""
    shown = shown_sections(saved.get("messages", []), instructions, policy)
    citations = Counter()
    for name, status in items.items():
        if name.startswith("cites:"):
            seen = "shown" if name.split(":", 1)[1] in shown else "never shown"
            citations[f"{seen}, {'cited' if status == 'passed' else 'not cited'}"] += 1
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
    }


def summarize(per_try: list[dict]) -> dict:
    total = {"citations": Counter(), "handoffs": Counter(), "proposals_after_receipt": 0}
    for d in per_try:
        total["citations"].update(d["citations"])
        total["handoffs"].update(d["handoffs"])
        total["proposals_after_receipt"] += d["proposals_after_receipt"]
    return {
        "citations": dict(sorted(total["citations"].items())),
        "handoffs": dict(sorted(total["handoffs"].items())),
        "proposals_after_receipt": total["proposals_after_receipt"],
    }
