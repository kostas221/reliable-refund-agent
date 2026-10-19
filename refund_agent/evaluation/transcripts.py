"""Readable transcripts of a run, for the dialogue audit (plan section 9):
`uv run python -m refund_agent.evaluation.transcripts runs/pilot-...`

Writes transcripts.md into the run folder: for each scenario, the simulated customer's instructions as sent and the
staff member's scripted decision; for each conversation, what the customer and the agent said, each tool call with
the essential part of its answer and, folded under it, the whole answer, the backend's notices, and the evaluator's
items, with the pending ones listed for the reader to mark. Text written by others that the agent read (a seller's
message, a rejection's reason) is shown in full. Text from the conversation is quoted as it was; nothing is
summarized (review of 2026-10-19: the reader could not see the seller's message, nor what the customer knew).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from refund_agent.evaluation.customers import simulator_instructions
from refund_agent.scenarios import Scenario, load_split

_ANSWER_KEYS = ("ok", "refused", "error", "status", "outcome", "amount_minor", "policy_citations", "explanation")


def _tool_answer(name: str, content: str) -> str:
    answer = json.loads(content)
    short = {key: answer[key] for key in _ANSWER_KEYS if key in answer}
    if "receipt" in answer:
        short["receipt"] = answer["receipt"]["receipt_number"]
    if "sections" in answer:
        short["sections"] = [section["citation"] for section in answer["sections"]]
    orders = answer.get("orders", []) + ([answer["order"]] if "order" in answer else [])
    if orders:
        short["orders"] = {o["order_id"]: [u["unit_id"] for u in o["units"]] for o in orders}
        sellers = {o["order_id"]: o["seller_message"]["untrusted_text"] for o in orders if "seller_message" in o}
        if sellers:
            short["seller_messages"] = sellers
    if "request" in answer:
        request = answer["request"]  # runs saved before 2026-10-19 have no rejection_reason
        short["request"] = {key: request[key] for key in ("status", "rejection_reason") if key in request}
    whole = json.dumps(answer, indent=2, ensure_ascii=False)
    return "\n".join(
        [
            f"- `{name}` answered: `{json.dumps(short, ensure_ascii=False)}`",
            "",
            "  <details><summary>full answer</summary>",
            "",
            "  ```json",
            *(f"  {line}" for line in whole.splitlines()),
            "  ```",
            "",
            "  </details>",
        ]
    )


def render_role(scenario: Scenario) -> list[str]:
    """What the simulated customer was told, as sent, and what the scripted staff member decides."""
    staff = scenario.staff.decision + (f', with the reason "{scenario.staff.note}"' if scenario.staff.note else "")
    return [
        f"## {scenario.id}: the simulated customer's instructions",
        "",
        f"Opening message, sent as written: {scenario.customer.opening_message}",
        "",
        f"Staff member, scripted: {staff}.",
        "",
        "<details><summary>instructions</summary>",
        "",
        "```text",
        *simulator_instructions(scenario).splitlines(),
        "```",
        "",
        "</details>",
        "",
    ]


def render_conversation(result: dict) -> list[str]:
    errors = [e for e in (result.get("system_error"), result.get("simulator_error")) if e]
    lines = [
        f"## {result['scenario']}{' try ' + str(result['try']) if 'try' in result else ''}: {result['result']}",
        "",
        f"Cost ${sum(result['spent_usd'].values()):.4f}; agent requests {result['agent_requests']}"
        + (f"; errors: {'; '.join(errors)}" if errors else ""),
        "",
    ]
    for message in result["messages"]:
        role = message["role"]
        if role == "customer":
            lines.append(f"**Customer:** {message['text']}")
        elif role == "event":
            lines.append(f"*Backend notice: {message['text']}*")
        elif role == "tool":
            lines.append(_tool_answer(message["name"], message["content"]))
        else:
            for call in message.get("tool_calls", []):
                lines.append(f"- agent calls `{call['name']}` `{call['arguments']}`")
            if message.get("text"):
                lines.append(f"**Agent:** {message['text']}")
        lines.append("")
    for status, title in (("failed", "Failed"), ("not_exercised", "Not exercised"), ("pending", "Pending")):
        items = [item for item in result["items"] if item["status"] == status]
        if items:
            lines += [f"{title} items:", ""]
            lines += [f"- [{status}] `{item['name']}`: {item['evidence']}" for item in items]
            lines.append("")
    return lines


def render_run(folder: Path) -> str:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    identity = manifest["identity"]
    lines = [
        f"# Transcripts of {folder.name}",
        "",
        f"Model {identity['model']}, agent reasoning {identity['agent_reasoning']}, simulator reasoning "
        f"{identity['simulator_reasoning']}, configuration {identity['configuration']}; code {manifest['git_commit']}, "
        f"fingerprint {manifest['fingerprint'][:12]}.",
        "",
    ]
    scenarios = {s.id: s for split in ("development", "held_out") for s in load_split(split)}
    shown: set[str] = set()
    for result_file in sorted(folder.glob("**/result.json")):  # D01/result.json, or D01/try1/result.json
        result = json.loads(result_file.read_text(encoding="utf-8"))
        if result["scenario"] not in shown and result["scenario"] in scenarios:
            shown.add(result["scenario"])
            lines += render_role(scenarios[result["scenario"]])
        lines += render_conversation(result)
    return "\n".join(lines)


def main() -> None:
    folder = Path(sys.argv[1])
    (folder / "transcripts.md").write_text(render_run(folder), encoding="utf-8", newline="\n")
    print(f"wrote {folder / 'transcripts.md'}")


if __name__ == "__main__":
    main()
