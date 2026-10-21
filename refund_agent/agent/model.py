"""The model adapter (plan sections 5 and 9): one small language for talking to any model.

The rest of the code speaks only this: messages as plain dicts, tool calls with a stable ID and JSON arguments, and
a ModelTurn with the answer and its token usage. An adapter translates it for one provider and holds no business
rule. ScriptedModel is the mock: it says the next line of a written script, costs nothing and always does the same,
so whole conversations can run without an API key. RecordingAdapter writes every request in full to a JSONL file,
so a prompt can be read exactly as the model received it before any paid run (plan section 12).

Messages:
    {"role": "customer", "text": ...}
    {"role": "agent", "text": ..., "tool_calls": [{"call_id", "name", "arguments"}], "continuation": [...]}
    {"role": "tool", "call_id": ..., "name": ..., "content": <JSON text>}
    {"role": "event", "text": ...}   a notice from the backend, for example that a request was approved
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from refund_agent.agent.costs import BudgetExceeded
from refund_agent.policy import REPO_ROOT, Policy
from refund_agent.scenarios import format_brl

# Version 2 widened when to cite (docs/pilot/results.md, second pilot). Version 3, after the dialogue audit of the
# runs before the freeze: ask which item the customer wants refunded, not which one was returned (D09), and pass on a
# rejection's reason. Version 4 (v1.1, step 1): the whole policy at the end, because in the final run of v1 the agent
# never cited a section its policy search had not shown it (docs/final/results.md). Version 5 (step 3), with policy
# v2: cite whenever an answer rests on the policy, hand off only in a case the policy names with its reason code, and
# the lifecycle rules of the policy v2 specification (docs/pilot/results.md, "v1.1 step 1"). Earlier versions stay
# for the runs made with them.
INSTRUCTIONS_PATH = REPO_ROOT / "prompts" / "agent-v7.md"


@dataclass(frozen=True)
class Instructions:
    text: str  # as the model receives it, the policy filled in
    version: str
    sha256: str  # of that text, so a manifest names the exact instructions, policy included


def policy_text(policy: Policy) -> str:
    """Every section under its citation ID, generated from the policy's one controlled source."""
    return "\n\n".join(
        f"{policy.citation(s.id)} ({s.title})\n{policy.rendered_text(s.id).strip()}" for s in policy.sections
    )


def load_instructions(path: Path = INSTRUCTIONS_PATH, policy: Policy | None = None) -> Instructions:
    """The instructions, with {policy_version} and {policy} filled in from the policy when the file asks for them.
    A file that asks for the policy is refused without one, so a placeholder never reaches a model."""
    text = path.read_text(encoding="utf-8")
    if "{policy}" in text:
        if policy is None:
            raise ValueError(f"{path.name} includes the policy: give the policy to load it")
        text = text.replace("{policy_version}", f"version {policy.version}").replace("{policy}", policy_text(policy))
    return Instructions(text, path.stem, hashlib.sha256(text.encode()).hexdigest())


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0  # billed at their own price (counted since 2026-10-19)
    output_tokens: int = 0
    reasoning_tokens: int = 0  # billed as output


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: tuple[dict, ...] = ()  # {"call_id", "name", "arguments"}
    usage: Usage = field(default_factory=Usage)
    model: str = ""  # the model that actually answered
    response_id: str | None = None
    continuation: tuple[Any, ...] = ()  # provider items to send back next time, such as reasoning items

    def as_message(self) -> dict:
        return {
            "role": "agent",
            "text": self.text,
            "tool_calls": list(self.tool_calls),
            "continuation": list(self.continuation),
        }


class ModelError(Exception):
    """The provider failed or answered unusably. A failure of the system, never hidden from the report (plan 11)."""

    def __init__(
        self,
        kind: Literal["rate_limit", "timeout", "server", "bad_request", "refusal", "invalid_output"],
        retryable: bool,
        detail: str = "",
    ) -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind, self.retryable, self.detail = kind, retryable, detail


class ModelAdapter(Protocol):
    name: str

    def respond(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> ModelTurn: ...


# The mock


@dataclass(frozen=True)
class Say:
    """A line of text for the customer. {tool.field} is filled in from that tool's latest result, and
    {tool.field|brl} shows centavos as money, for example R$ 49,90."""

    text: str


@dataclass(frozen=True)
class Call:
    """A tool call. Argument values may hold {tool.field} placeholders, filled in from that tool's latest result."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


_PLACEHOLDER = re.compile(r"\{([a-z_]+)((?:\.[a-z_0-9]+)+)(\|brl)?\}")


class ScriptedModel:
    """Says the next line of its script each time it is asked. Running out of lines is an error, so a script that
    does not fit the conversation fails loudly instead of improvising."""

    name = "scripted"

    def __init__(self, script: Sequence[Say | Call]) -> None:
        self.script = list(script)
        self.requests: list[dict] = []  # what it was asked, for tests

    def respond(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> ModelTurn:
        self.requests.append({"instructions": instructions, "messages": list(messages), "tools": list(tools)})
        # The line to say is the number of agent turns so far, so asking again after a restart repeats the same line.
        index = sum(1 for m in messages if m["role"] == "agent")
        if index >= len(self.script):
            raise ModelError("invalid_output", retryable=False, detail=f"the script has no line {index + 1}")
        line = self.script[index]
        if isinstance(line, Say):
            return ModelTurn(text=_fill(line.text, messages), model=self.name)
        arguments = {key: _fill_value(value, messages) for key, value in line.arguments.items()}
        call = {"call_id": f"scripted-{index + 1}", "name": line.name, "arguments": json.dumps(arguments)}
        return ModelTurn(text="", tool_calls=(call,), model=self.name)


def _latest_result(messages: Sequence[dict], tool: str) -> dict:
    for message in reversed(messages):
        if message["role"] == "tool" and message["name"] == tool:
            return json.loads(message["content"])
    raise ModelError("invalid_output", retryable=False, detail=f"the script needs a result of {tool} that is not there")


def _lookup(messages: Sequence[dict], tool: str, path: str) -> Any:
    value: Any = _latest_result(messages, tool)
    for key in path.strip(".").split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _fill(text: str, messages: Sequence[dict]) -> str:
    def show(match: re.Match[str]) -> str:
        value = _lookup(messages, match.group(1), match.group(2))
        return format_brl(value) if match.group(3) else str(value)

    return _PLACEHOLDER.sub(show, text)


def _fill_value(value: Any, messages: Sequence[dict]) -> Any:
    if isinstance(value, str):
        whole = _PLACEHOLDER.fullmatch(value)
        return _lookup(messages, whole.group(1), whole.group(2)) if whole else _fill(value, messages)
    if isinstance(value, list):
        return [_fill_value(item, messages) for item in value]
    return value


# The log


class RecordingAdapter:
    """Writes each request and its answer, in full, as one JSON line, then passes the answer on unchanged."""

    def __init__(self, inner: ModelAdapter, path: Path) -> None:
        self.inner, self.path, self.name = inner, path, inner.name

    def respond(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> ModelTurn:
        record = {
            "at": datetime.now(UTC).isoformat(),
            "adapter": self.inner.name,
            "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
            "instructions": instructions,
            "messages": list(messages),
            "tools": list(tools),
        }
        try:
            turn = self.inner.respond(instructions, messages, tools)
        except ModelError as error:
            record["error"] = {"kind": error.kind, "retryable": error.retryable, "detail": error.detail}
            self._write(self._attempts(record))
            raise
        except BudgetExceeded as stop:  # a stop is logged too, with what was tried before it
            record["error"] = {"kind": "budget_exceeded", "retryable": False, "detail": str(stop)}
            self._write(self._attempts(record))
            raise
        record["answer"] = {"text": turn.text, "tool_calls": list(turn.tool_calls), "model": turn.model}
        record["usage"] = asdict(turn.usage)
        self._write(self._attempts(record))
        return turn

    def _attempts(self, record: dict) -> dict:
        """Every attempt of an adapter that retries, with its outcome and counted cost (review of 2026-10-15)."""
        attempts = getattr(self.inner, "last_attempts", None)
        return record if attempts is None else {**record, "attempts": list(attempts)}

    def _write(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as log:
            log.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
