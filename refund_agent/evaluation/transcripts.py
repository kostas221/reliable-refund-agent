"""Readable transcripts of a run, for the dialogue audit (plan section 9):
`uv run python -m refund_agent.evaluation.transcripts runs/pilot-...`

Writes transcripts.md into the run folder: for each conversation, what the customer and the agent said, each tool
call with the essential part of its answer, the backend's notices, and the evaluator's items, with the pending ones
listed for the reader to mark. Text from the conversation is quoted as it was; nothing is summarized.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ANSWER_KEYS = ("ok", "refused", "error", "status", "outcome", "amount_minor", "policy_citations", "explanation")


def _tool_answer(name: str, content: str) -> str:
    answer = json.loads(content)
    short = {key: answer[key] for key in _ANSWER_KEYS if key in answer}
    if "receipt" in answer:
        short["receipt"] = answer["receipt"]["receipt_number"]
    if "sections" in answer:
        short["sections"] = [section["citation"] for section in answer["sections"]]
    if "orders" in answer:
        short["orders"] = {o["order_id"]: [u["unit_id"] for u in o["units"]] for o in answer["orders"]}
    return f"- `{name}` answered: `{json.dumps(short, ensure_ascii=False)}`"


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
    for status in ("failed", "pending"):
        items = [item for item in result["items"] if item["status"] == status]
        if items:
            lines += [f"{status.capitalize()} items:", ""]
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
    for result_file in sorted(folder.glob("**/result.json")):  # D01/result.json, or D01/try1/result.json
        lines += render_conversation(json.loads(result_file.read_text(encoding="utf-8")))
    return "\n".join(lines)


def main() -> None:
    folder = Path(sys.argv[1])
    (folder / "transcripts.md").write_text(render_run(folder), encoding="utf-8", newline="\n")
    print(f"wrote {folder / 'transcripts.md'}")


if __name__ == "__main__":
    main()
