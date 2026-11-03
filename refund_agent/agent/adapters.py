"""Which adapter serves a model, and which key it needs. A model whose name begins with "claude-" is served by the
Anthropic Messages API (anthropic_adapter.py), every other by the OpenAI Responses API (openai_adapter.py). The
runners and the live server build their adapters here, so the Sol-Sonnet comparison changes a model name and
nothing else."""

from __future__ import annotations

import os

from refund_agent.agent.anthropic_adapter import AnthropicMessages
from refund_agent.agent.costs import Budget
from refund_agent.agent.openai_adapter import OpenAIResponses

KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def provider(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "openai"


def model_adapter(
    model: str, reasoning: str | None, *, role: str = "agent", budget: Budget | None = None
) -> OpenAIResponses | AnthropicMessages:
    """reasoning: OpenAI's reasoning effort, or Anthropic's effort; "low" names the same setting for both."""
    if provider(model) == "anthropic":
        return AnthropicMessages(model, reasoning, role=role, budget=budget)
    return OpenAIResponses(model, reasoning, role=role, budget=budget)


def missing_key(*models: str) -> str | None:
    """The first key these models need that is not in the environment, or None. Only its presence is checked; it
    is never read or printed."""
    for model in models:
        key = KEYS[provider(model)]
        if not os.environ.get(key, "").strip():
            return key
    return None
