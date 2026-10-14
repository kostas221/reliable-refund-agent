"""The model adapter for the OpenAI Responses API (plan section 9). It holds no business rule.

request() builds exactly what would be sent, without sending it, so a dry run can write it to a file and a person can
read it in full before any paid run. respond() sends it and translates the answer back:

- Nothing is stored at OpenAI (store false). What the model needs to continue, including its reasoning items in
  encrypted form, travels back in the conversation's own checkpoint as the agent message's continuation.
- One tool call per answer (parallel tool calls off), like the scripted model, so every step is one action.
- The SDK's own retries are off. Retries happen here, are counted, and wait a little longer each time.
- The tools are offered with strict schemas reduced to structure, types and descriptions; length and count limits are
  left to the tool executor, which checks every argument anyway. The model's schema is never the authority.
- The budget is checked before every request against its worst case, and settled with the usage reported.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

import openai

from refund_agent.agent.costs import Budget, cost_usd, estimated_tokens
from refund_agent.agent.model import ModelError, ModelTurn, Usage

_KEEP = {"type", "properties", "required", "additionalProperties", "description", "items", "enum"}
_RETRYABLE = {
    openai.RateLimitError: "rate_limit",
    openai.APITimeoutError: "timeout",
    openai.APIConnectionError: "server",
    openai.InternalServerError: "server",
}


def strict_schema(schema: dict) -> dict:
    """The structure of a tool's arguments for the model: every property required, no extra ones, no limits."""
    reduced = {key: value for key, value in schema.items() if key in _KEEP}
    if "properties" in reduced:
        reduced["properties"] = {name: strict_schema(prop) for name, prop in reduced["properties"].items()}
        reduced["required"] = list(reduced["properties"])
        reduced["additionalProperties"] = False
    if "items" in reduced:
        reduced["items"] = strict_schema(reduced["items"])
    return reduced


def to_input(messages: Sequence[dict]) -> list[dict]:
    """Our messages as Responses API input items, in order."""
    items: list[dict] = []
    for message in messages:
        role = message["role"]
        if role == "customer":
            items.append({"role": "user", "content": message["text"]})
        elif role == "event":
            items.append({"role": "developer", "content": f"Notice from the shop's backend: {message['text']}"})
        elif role == "agent":
            items.extend(message.get("continuation", []))  # reasoning items come before what they produced
            if message.get("text"):
                items.append({"role": "assistant", "content": message["text"]})
            for call in message.get("tool_calls", []):
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call["call_id"],
                        "name": call["name"],
                        "arguments": call["arguments"],
                    }
                )
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": message["call_id"], "output": message["content"]})
        else:
            raise ValueError(f"unknown message role {role!r}")
    return items


class OpenAIResponses:
    def __init__(
        self,
        model: str,
        reasoning: str | None,
        *,
        role: str = "agent",
        budget: Budget | None = None,
        client: Any = None,
        max_output_tokens: int = 4000,
        retries: int = 3,
        timeout_s: float = 90.0,
    ) -> None:
        """reasoning: an effort such as "low" or "none", or None for the model's default. role: "agent" or
        "simulator", for the budget's split. client: the OpenAI client; tests pass a fake one."""
        self.model, self.reasoning, self.role, self.budget = model, reasoning, role, budget
        self.name = f"{model}/{reasoning or 'default'}"
        self.max_output_tokens, self.retries = max_output_tokens, retries
        self._client = client
        self._timeout_s = timeout_s
        self.retries_used = 0

    @property
    def client(self) -> Any:
        if self._client is None:  # created only when a request is really sent: a dry run needs no key
            self._client = openai.OpenAI(max_retries=0, timeout=self._timeout_s)
        return self._client

    def request(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> dict:
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": to_input(messages),
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "max_output_tokens": self.max_output_tokens,
        }
        if tools:
            request["tools"] = [
                {
                    "type": "function",
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": strict_schema(tool["parameters"]),
                    "strict": True,
                }
                for tool in tools
            ]
            request["parallel_tool_calls"] = False
        if self.reasoning is not None:
            request["reasoning"] = {"effort": self.reasoning}
        return request

    def worst_case_usd(self, request: dict) -> float:
        tokens = estimated_tokens(json.dumps(request, ensure_ascii=False))
        return cost_usd(self.model, tokens, 0, self.max_output_tokens)

    def respond(self, instructions: str, messages: Sequence[dict], tools: Sequence[dict]) -> ModelTurn:
        request = self.request(instructions, messages, tools)
        worst = self.worst_case_usd(request)
        if self.budget is not None:
            self.budget.reserve(worst)
        response = self._send(request)
        turn = parse(response)
        if self.budget is not None:
            usage = turn.usage
            spent = (
                worst
                if getattr(response, "usage", None) is None
                else cost_usd(self.model, usage.input_tokens, usage.cached_input_tokens, usage.output_tokens)
            )
            self.budget.settle(self.role, spent)
        return turn

    def _send(self, request: dict) -> Any:
        for attempt in range(self.retries + 1):
            try:
                return self.client.responses.create(**request)
            except tuple(_RETRYABLE) as error:
                kind = next(k for cls, k in _RETRYABLE.items() if isinstance(error, cls))
                if attempt == self.retries:
                    raise ModelError(kind, retryable=True, detail=str(error)) from error
                self.retries_used += 1
                time.sleep(2**attempt)
            except openai.APIStatusError as error:  # bad request, authentication, permission, not found
                raise ModelError("bad_request", retryable=False, detail=f"{error.status_code}: {error}") from error
        raise AssertionError("unreachable")


def parse(response: Any) -> ModelTurn:
    """The answer as a ModelTurn: text or one tool call, the reasoning to carry on, and the usage."""
    if getattr(response, "status", "completed") not in (None, "completed"):
        reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
        raise ModelError("invalid_output", retryable=False, detail=f"response {response.status}: {reason}")
    texts, refusals, calls, continuation = [], [], [], []
    for item in response.output:
        if item.type == "reasoning":
            continuation.append(item.model_dump(mode="json", exclude_none=True))
        elif item.type == "function_call":
            calls.append({"call_id": item.call_id, "name": item.name, "arguments": item.arguments})
        elif item.type == "message":
            for part in item.content:
                (refusals if part.type == "refusal" else texts).append(getattr(part, "refusal", None) or part.text)
    if refusals and not texts and not calls:
        raise ModelError("refusal", retryable=False, detail=" ".join(refusals))
    if not texts and not calls:
        raise ModelError("invalid_output", retryable=False, detail="neither text nor a tool call")
    usage = response.usage
    return ModelTurn(
        text="\n".join(texts),
        tool_calls=tuple(calls),
        usage=Usage(
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.input_tokens_details.cached_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        )
        if usage is not None
        else Usage(),
        model=response.model,
        response_id=response.id,
        continuation=tuple(continuation),
    )
