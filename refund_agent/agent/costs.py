"""Token prices and the budget that stops a paid run before it spends more than allowed (plan section 12).

The budget is checked before every attempt to send a model request, retries included, against that request's worst
case: its whole input at the uncached price plus the most output it may produce. So a run stops before an attempt
that could cross the limit, not after. Each attempt is counted as soon as it ends, before its answer is read, since
an answer that turns out unusable was still billed; an attempt whose charge is unknown (a timeout, a lost connection,
a server error, an answer without usage) counts its worst case, kept apart as uncertain (outside review of
2026-10-15). It holds within one process, where requests run one at a time. The provider's own usage page remains
the record of what was billed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1M tokens: (input, cached input, output). List prices as recorded on 2026-10-07 in the Agent Action Guard
# project; the pilot command makes the person running it confirm the date they checked them (plan section 12).
PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-sol": (2.00, 0.20, 10.00),
}


class BudgetExceeded(Exception):
    """The next request could cross the budget, so it was not sent."""


def cost_usd(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """output_tokens include reasoning tokens, which are billed as output."""
    price_input, price_cached, price_output = PRICES[model]
    fresh = input_tokens - cached_tokens
    return (fresh * price_input + cached_tokens * price_cached + output_tokens * price_output) / 1_000_000


def estimated_tokens(text: str) -> int:
    """A deliberately high estimate: about three characters per token, where English averages about four."""
    return len(text) // 3 + 1


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0  # what was counted, including the uncertain part
    requests: int = 0  # attempts sent, retries included
    uncertain_usd: float = 0.0  # worst cases counted for attempts whose charge is unknown
    by_role: dict[str, float] = field(default_factory=dict)  # agent, simulator: spent separately (plan section 12)

    def reserve(self, worst_case_usd: float) -> None:
        if self.spent_usd + worst_case_usd > self.limit_usd:
            raise BudgetExceeded(
                f"spent ${self.spent_usd:.4f}; the next request could cost up to ${worst_case_usd:.4f}, "
                f"over the limit of ${self.limit_usd:.2f}"
            )

    def settle(self, role: str, usd: float, *, uncertain: bool = False) -> None:
        self.spent_usd += usd
        self.requests += 1
        if uncertain:
            self.uncertain_usd += usd
        self.by_role[role] = self.by_role.get(role, 0.0) + usd
