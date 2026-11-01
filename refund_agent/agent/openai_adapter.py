"""The model adapter for the OpenAI Responses API (plan section 9). It holds no business rule.

request() builds exactly what would be sent, without sending it, so a dry run can write it to a file and a person can
read it in full before any paid run. respond() sends it and translates the answer back:

- Nothing is stored at OpenAI (store false). What the model needs to continue, including its reasoning items in
  encrypted form, travels back in the conversation's own checkpoint as the agent message's continuation.
- One tool call per answer (parallel tool calls off), like the scripted model, so every step is one action.
- The SDK's own retries are off. Retries happen here, are counted, and wait a little longer each time; every
  attempt is listed in last_attempts, for the request log.
- The tools are offered with strict schemas reduced to structure, types and descriptions; length and count limits are
  left to the tool executor, which checks every argument anyway. The model's schema is never the authority.
- The budget is checked before every attempt against the request's worst case, and each attempt is settled as soon
  as it ends, before its answer is read: with the usage reported, or with the worst case when the charge is unknown.
- A refusal for lack of credit (HTTP 429, insufficient_quota) is not retried and raises OutOfCredit, a stop like the
  budget's: the Sol confirmation run of 2026-11-01 went on after it with tries that tested nothing.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

import openai

from refund_agent.agent.costs import Budget, OutOfCredit, cost_usd, estimated_tokens
from refund_agent.agent.model import ModelError, ModelTurn, Usage

_KEEP = {"type", "properties", "required", "additionalProperties", "description", "items", "enum"}
_RETRYABLE = {
    openai.RateLimitError: "rate_limit",
    openai.APITimeoutError: "timeout",
    openai.APIConnectionError: "server",
    openai.InternalServerError: "server",
}
# The provider's marks of an account with no credit left; recorded on 2026-11-01: type insufficient_quota, code
# credit_balance_exhausted ("You have no credits remaining").
_NO_CREDIT = {"insufficient_quota", "credit_balance_exhausted"}


def out_of_credit(error: Exception) -> bool:
    """A rate-limit answer that is really an empty account: waiting and retrying cannot help."""
    marks = {getattr(error, "type", None), getattr(error, "code", None)}
    return isinstance(error, openai.RateLimitError) and bool(marks & _NO_CREDIT)


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
            # Reasoning items come before what they produced; labelled text is among them, in the order the model gave
            # it, so the model gets back what it said, not only what the customer was shown.
            carried = message.get("continuation", [])
            items.extend(carried)
            if message.get("text") and not any(item.get("role") == "assistant" for item in carried):
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
        self.last_attempts: list[dict] = []  # the attempts of the latest request: outcome, cost, whether it is certain

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
                response = self.client.responses.create(**request)
            except tuple(_RETRYABLE) as error:
                if out_of_credit(error):  # refused before any work, as every retry would be
                    self._settle("no_credit", 0.0, worst)
                    stop = f"the provider refused the request: no credit left ({error})"
                    if self.budget is not None:
                        self.budget.refused_for_credit(stop)
                    raise OutOfCredit(stop) from error
                kind = next(k for cls, k in _RETRYABLE.items() if isinstance(error, cls))
                # A rate limit refuses the request before any work; after a timeout, a lost connection or a server
                # error nobody knows what was billed, so the worst case is counted.
                unknown = kind != "rate_limit"
                self._settle(kind, worst if unknown else 0.0, worst, uncertain=unknown)
                if attempt == self.retries:
                    raise ModelError(kind, retryable=True, detail=str(error)) from error
                self.retries_used += 1
                time.sleep(2**attempt)
                continue
            except openai.APIStatusError as error:  # bad request, authentication, permission, not found
                self._settle("bad_request", 0.0, worst)
                request = getattr(error, "request_id", None)  # the provider's ID of this request, if it sent one
                detail = f"{error.status_code}: {error}" + (f" (request {request})" if request else "")
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
        usage = getattr(response, "usage", None)
        try:
            details = usage.input_tokens_details
            return cost_usd(
                self.model,
                usage.input_tokens,
                details.cached_tokens,
                usage.output_tokens,
                cache_write_tokens=getattr(details, "cache_write_tokens", 0) or 0,
            )
        except AttributeError:  # no usage, or not the usual shape: the charge is unknown
            return None

    def _settle(self, outcome: str, usd: float, reserved: float, *, uncertain: bool = False) -> None:
        self.last_attempts.append({"outcome": outcome, "usd": usd, "uncertain": uncertain})
        if self.budget is not None:
            self.budget.settle(self.role, usd, uncertain=uncertain, reserved=reserved)


def parse(response: Any) -> ModelTurn:
    """The answer as a ModelTurn: text or one tool call, the reasoning to carry on, and the usage.

    The customer sees the final answer: when the model labels some text final_answer, the text it labels commentary
    is left out of what is shown. What the model said stays whole: every text item with its label, in order, goes to
    the log (message_items) and, when the model labels its text, back to the model with the reasoning items in the
    order it produced them (continuation), as the provider asks. Unlabelled text is shown and sent back as it is.
    Labelled text the model repeats word for word right after itself is shown once; the log and the continuation keep
    both (plan change log, 2026-10-29).
    """
    if getattr(response, "status", "completed") not in (None, "completed"):
        reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
        raise ModelError("invalid_output", retryable=False, detail=f"response {response.status}: {reason}")
    labels = any(getattr(item, "phase", None) for item in response.output if item.type == "message")
    labelled, refusals, calls, continuation = [], [], [], []
    for item in response.output:
        if item.type == "reasoning":
            continuation.append(item.model_dump(mode="json", exclude_none=True))
        elif item.type == "function_call":
            calls.append({"call_id": item.call_id, "name": item.name, "arguments": item.arguments})
        elif item.type == "message":
            phase = getattr(item, "phase", None)
            for part in item.content:
                if part.type == "refusal":
                    refusals.append(part.refusal)
                    continue
                labelled.append({"phase": phase, "text": part.text})
                if labels:
                    said = {"role": "assistant", "content": part.text}
                    continuation.append({**said, "phase": phase} if phase else said)
    final = [entry["text"] for entry in labelled if entry["phase"] == "final_answer"]
    texts = final or [entry["text"] for entry in labelled]
    if labels:
        # D09 try 2 of runs/pilot-20261029T113311Z-gpt-6-luna-none: the same final answer twice in one response (the
        # only one of 2,242 labelled answers of the development runs since 2026-10-22), so the customer saw the question
        # twice. What goes back to the model is the continuation, so only what is shown changes.
        texts = [said for n, said in enumerate(texts) if n == 0 or said != texts[n - 1]]
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
            cache_write_tokens=getattr(usage.input_tokens_details, "cache_write_tokens", 0) or 0,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        )
        if usage is not None
        else Usage(),
        model=response.model,
        response_id=response.id,
        continuation=tuple(continuation),
        message_items=tuple(labelled),
    )
