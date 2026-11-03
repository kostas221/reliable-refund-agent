"""The model adapter for the Anthropic Messages API (Claude Sonnet 5.5), the second model of the Sol-Sonnet comparison
(plan change log, 2026-11-02). It holds no business rule and keeps the contract of OpenAIResponses, so the comparison
changes the model and nothing else:

- request() builds exactly what would be sent, without sending it, so a dry run can write it to a file and a person
  can read it in full before any paid run. respond() sends it and translates the answer back.
- The same tools with the same reduced strict schemas, one tool call per answer (parallel tool use off), the same
  output limit (4,000 tokens, thinking included), the SDK's own retries off and ours counted, the budget reserved
  before every attempt and settled as soon as it ends, and a refusal for lack of credit raised as OutOfCredit.
- Reasoning: the model's adaptive thinking at the given effort (`output_config.effort`, "low" in the comparison);
  nothing else is set, so the model's own thinking mode is the one compared.
- Caching, as OpenAI caches a repeated prefix by itself: a cache mark on the instructions, so the tools and
  instructions every conversation shares are written to the cache once and read after, and the API's automatic mark
  on the request, which caches each conversation as it grows. Without the first, every conversation wrote the same
  instructions to the cache again: in the first check of 65 development conversations (2026-11-03) cache writes
  were 21% of the input against Sol's 4%, and the agent cost $0.029 a conversation against Sol's $0.006. A cache write
  is billed at 1.25 times the input price and counted that way; the marks change what is billed, not what is sent.
- What the model must get back: every block of its answer, thinking blocks included, unchanged and in order, travels
  in the agent message's continuation. The API checks that nothing before a thinking block changed since it was made,
  so the history is only ever appended to: each of our messages becomes one API message, built the same way on every
  request (tests/test_anthropic_adapter.py checks that each request begins with the whole previous one).

Two differences of the API are recorded, not hidden. A notice from the shop's backend (a staff decision, a button)
goes as a user message that says it is from the backend: OpenAI's developer role has no counterpart there, and the
API's mid-conversation system message cannot follow the agent's answer, which is where notices arrive. And the
provider's refusal for lack of credit is HTTP 402 `billing_error` (an older form is a 400 that says the credit
balance is too low).
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

import anthropic

from refund_agent.agent.costs import Budget, OutOfCredit, cost_usd, estimated_tokens
from refund_agent.agent.model import ModelError, ModelTurn, Usage
from refund_agent.agent.openai_adapter import strict_schema

NOTICE = "Notice from the shop's backend: "


def out_of_credit(error: Exception) -> bool:
    """The account has no credit left: retrying cannot help."""
    if not isinstance(error, anthropic.APIStatusError):
        return False
    if error.status_code == 402 or error.type == "billing_error":
        return True
    return error.status_code == 400 and "credit balance" in str(error).lower()


def to_messages(messages: Sequence[dict]) -> list[dict]:
    """Our messages as Messages API messages, one for one, in order. The API joins consecutive messages of one role
    into one turn, so a tool result followed by the customer's next message, or an answer followed by a fact line,
    needs no merging here, and an earlier message is never rewritten when a later one is added."""
    out: list[dict] = []
    for message in messages:
        role = message["role"]
        if role == "customer":
            out.append({"role": "user", "content": [{"type": "text", "text": message["text"]}]})
        elif role == "event":
            out.append({"role": "user", "content": [{"type": "text", "text": NOTICE + message["text"]}]})
        elif role == "agent":
            content = list(message.get("continuation", []))
            if not content:  # a fact line, or an answer that carried nothing back
                if message.get("text"):
                    content.append({"type": "text", "text": message["text"]})
                for call in message.get("tool_calls", []):
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call["call_id"],
                            "name": call["name"],
                            "input": json.loads(call["arguments"] or "{}"),
                        }
                    )
            if content:
                out.append({"role": "assistant", "content": content})
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": message["call_id"], "content": message["content"]}
                    ],
                }
            )
        else:
            raise ValueError(f"unknown message role {role!r}")
    return out


class AnthropicMessages:
    def __init__(
        self,
        model: str,
        effort: str | None,
        *,
        role: str = "agent",
        budget: Budget | None = None,
        client: Any = None,
        max_output_tokens: int = 4000,
        retries: int = 3,
        timeout_s: float = 90.0,
    ) -> None:
        """effort: "low" to "max", or None for the model's default. role: "agent" or "simulator", for the budget's
        split. client: the Anthropic client; tests pass a fake one."""
        self.model, self.effort, self.role, self.budget = model, effort, role, budget
        self.name = f"{model}/{effort or 'default'}"
        self.max_output_tokens, self.retries = max_output_tokens, retries
        self._client = client
        self._timeout_s = timeout_s
        self.retries_used = 0
        self.last_attempts: list[dict] = []  # the attempts of the latest request: outcome, cost, whether it is certain

    @property
    def client(self) -> Any:
        if self._client is None:  # created only when a request is really sent: a dry run needs no key
            self._client = anthropic.Anthropic(max_retries=0, timeout=self._timeout_s)
        return self._client

    def request(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> dict:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            # Marked, so the tools and instructions shared by every conversation are cached once (module docstring).
            "system": [{"type": "text", "text": instructions, "cache_control": {"type": "ephemeral"}}],
            "messages": to_messages(messages),
            "cache_control": {"type": "ephemeral"},
        }
        if tools:
            request["tools"] = [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": strict_schema(tool["parameters"]),
                    "strict": True,
                }
                for tool in tools
            ]
            request["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
        if self.effort is not None:
            request["output_config"] = {"effort": self.effort}
        return request

    def worst_case_usd(self, request: dict) -> float:
        tokens = estimated_tokens(json.dumps(request, ensure_ascii=False))
        # Every input token at the dearest input price, a cache write: still a bound if the provider writes them all.
        return cost_usd(self.model, tokens, 0, self.max_output_tokens, cache_write_tokens=tokens)

    def respond(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> ModelTurn:
        return parse(self._send(self.request(instructions, messages, tools)))

    def _send(self, request: dict) -> Any:
        """Send with our retries. Each attempt reserves the worst case first and is settled as soon as it ends."""
        worst = self.worst_case_usd(request)
        self.last_attempts = []
        for attempt in range(self.retries + 1):
            if self.budget is not None:
                self.budget.reserve(worst)
            try:
                response = self.client.messages.create(**request)
            except anthropic.APIConnectionError as error:  # a timeout or a lost connection: the charge is unknown
                kind = "timeout" if isinstance(error, anthropic.APITimeoutError) else "server"
                self._settle(kind, worst, worst, uncertain=True)
                if attempt == self.retries:
                    raise ModelError(kind, retryable=True, detail=str(error)) from error
                self.retries_used += 1
                time.sleep(2**attempt)
                continue
            except anthropic.APIStatusError as error:
                if out_of_credit(error):  # refused before any work, as every retry would be
                    self._settle("no_credit", 0.0, worst)
                    stop = f"the provider refused the request: no credit left ({error})"
                    if self.budget is not None:
                        self.budget.refused_for_credit(stop)
                    raise OutOfCredit(stop) from error
                if error.status_code == 429 or error.status_code >= 500:
                    # A rate limit refuses the request before any work; after a server error (overloaded included)
                    # nobody knows what was billed, so the worst case is counted.
                    kind = "rate_limit" if error.status_code == 429 else "server"
                    unknown = kind == "server"
                    self._settle(kind, worst if unknown else 0.0, worst, uncertain=unknown)
                    if attempt == self.retries:
                        raise ModelError(kind, retryable=True, detail=str(error)) from error
                    self.retries_used += 1
                    time.sleep(2**attempt)
                    continue
                self._settle("bad_request", 0.0, worst)  # bad request, authentication, permission, not found
                request_id = getattr(error, "request_id", None)
                detail = f"{error.status_code}: {error}" + (f" (request {request_id})" if request_id else "")
                raise ModelError("bad_request", retryable=False, detail=detail) from error
            except Exception:  # anything else: what was billed is unknown, and what was held is released
                self._settle("unknown", worst, worst, uncertain=True)
                raise
            spent = self._reported_cost(response)
            self._settle("answered", worst if spent is None else spent, worst, uncertain=spent is None)
            return response
        raise AssertionError("unreachable")

    def _reported_cost(self, response: Any) -> float | None:
        """The cost the answer's usage reports, read before the answer itself: an unusable answer was still billed."""
        usage = usage_of(response)
        if usage is None:
            return None
        return cost_usd(
            self.model,
            usage.input_tokens,
            usage.cached_input_tokens,
            usage.output_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )

    def _settle(self, outcome: str, usd: float, reserved: float, *, uncertain: bool = False) -> None:
        self.last_attempts.append({"outcome": outcome, "usd": usd, "uncertain": uncertain})
        if self.budget is not None:
            self.budget.settle(self.role, usd, uncertain=uncertain, reserved=reserved)


def usage_of(response: Any) -> Usage | None:
    """The answer's usage in our terms: input_tokens counts every input token, cached and cache-written ones
    included (the API reports those three apart); None when the answer carries no usage."""
    usage = getattr(response, "usage", None)
    try:
        written = usage.cache_creation_input_tokens or 0
        read = usage.cache_read_input_tokens or 0
        details = getattr(usage, "output_tokens_details", None)
        return Usage(
            input_tokens=usage.input_tokens + written + read,
            cached_input_tokens=read,
            cache_write_tokens=written,
            output_tokens=usage.output_tokens,
            reasoning_tokens=(getattr(details, "thinking_tokens", 0) or 0) if details is not None else 0,
        )
    except AttributeError:  # no usage, or not the usual shape: the charge is unknown
        return None


def block_to_input(block: Any) -> dict:
    """One block of an answer as it is sent back: its own fields, unchanged."""
    if block.type == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if block.type == "redacted_thinking":
        return {"type": "redacted_thinking", "data": block.data}
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump(mode="json", exclude_none=True)


def parse(response: Any) -> ModelTurn:
    """The answer as a ModelTurn: its text and its one tool call, every block to carry back, and the usage. A refusal
    and an answer cut at the output limit are model errors, as an incomplete answer is from OpenAI."""
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None)
        raise ModelError("refusal", retryable=False, detail=f"category {category}")
    if response.stop_reason == "max_tokens":
        raise ModelError("invalid_output", retryable=False, detail="response incomplete: max_tokens")
    texts, calls, continuation, items = [], [], [], []
    for block in response.content:
        if block.type == "text" and not block.text:
            continue  # the API refuses an empty text block sent back; skipped the same way on every request
        continuation.append(block_to_input(block))
        if block.type == "text":
            texts.append(block.text)
            items.append({"phase": None, "text": block.text})
        elif block.type == "tool_use":
            calls.append({"call_id": block.id, "name": block.name, "arguments": json.dumps(block.input)})
    if not texts and not calls:
        raise ModelError(
            "invalid_output", retryable=False, detail=f"neither text nor a tool call ({response.stop_reason})"
        )
    return ModelTurn(
        text="\n".join(texts),
        tool_calls=tuple(calls),
        usage=usage_of(response) or Usage(),
        model=response.model,
        response_id=response.id,
        continuation=tuple(continuation),
        message_items=tuple(items),
    )
