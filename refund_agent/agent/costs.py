"""Token prices and the budget that stops a paid run before it spends more than allowed (plan section 12).

The budget is checked before every attempt to send a model request, retries included, against that request's worst
case: its whole input at the uncached price plus the most output it may produce. So a run stops before an attempt
that could cross the limit, not after. Each attempt is counted as soon as it ends, before its answer is read, since
an answer that turns out unusable was still billed; an attempt whose charge is unknown (a timeout, a lost connection,
a server error, an answer without usage) counts its worst case, kept apart as uncertain (outside review of
2026-10-15). The provider's own usage page remains the record of what was billed.

One budget can be shared by requests that run at the same time: in the live server a customer's message and a staff
decision delivered from the background both call the model (outside critique of the closing plan, 2026-11-01). Each
attempt holds its worst case against the limit from its reservation until it is settled, under a lock, so two
attempts in flight can never pass the limit together. A budget given `record` hands each settled attempt to it, so
the live server keeps what was spent in its database and a restart goes on from there instead of from zero.

The worst case is an upper bound, not an average (review of 2026-10-19, R6): no token is shorter than one byte of
UTF-8 text, so the input counts one token per byte of the request, plus a margin for the provider's own framing. An
attempt whose reported cost still exceeds what was reserved for it is recorded, and no request is sent after it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

# USD per 1M tokens: (input, cached input, cache writes, output), standard tier, as the user read them on the
# models' pages on 2026-10-19. They corrected what was recorded on 2026-10-07: Sol's cached input is $0.10, not $0.20,
# and cache writes, 1.25 times the input price, were not counted before. The paid commands make the person running
# them confirm the date they checked the prices (plan section 12).
PRICES: dict[str, tuple[float, float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.125, 0.50),
    "gpt-6.1-sol": (2.00, 0.10, 2.50, 10.00),
}


class BudgetExceeded(Exception):
    """The next request could cross the budget, so it was not sent."""


class OutOfCredit(BudgetExceeded):
    """The provider refused a request because the account has no credit left (HTTP 429, type insufficient_quota).
    A stop like the budget's, not a failure of the agent: every later request would be refused the same way. In the
    Sol confirmation run of 2026-11-01 the runner went on after it and recorded 83 tries that tested nothing."""


def cost_usd(
    model: str, input_tokens: int, cached_tokens: int, output_tokens: int, cache_write_tokens: int = 0
) -> float:
    """input_tokens include the cached and the cache-written ones, each billed at its own price; output_tokens
    include reasoning tokens, which are billed as output."""
    price_input, price_cached, price_write, price_output = PRICES[model]
    fresh = input_tokens - cached_tokens - cache_write_tokens
    paid = fresh * price_input + cached_tokens * price_cached + cache_write_tokens * price_write
    return (paid + output_tokens * price_output) / 1_000_000


FRAMING_TOKENS = 256  # the provider's own markers around instructions, messages and tools, generously


def estimated_tokens(text: str) -> int:
    """An upper bound on the tokens of this text: one per byte of UTF-8, where English averages about four bytes a
    token, plus the framing margin."""
    return len(text.encode("utf-8")) + FRAMING_TOKENS


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0  # what was counted, including the uncertain part
    requests: int = 0  # attempts sent, retries included
    uncertain_usd: float = 0.0  # worst cases counted for attempts whose charge is unknown
    by_role: dict[str, float] = field(default_factory=dict)  # agent, simulator: spent separately (plan section 12)
    overrun: str | None = None  # an attempt cost more than its reserved worst case: nothing more is sent
    held_usd: float = 0.0  # worst cases of attempts reserved and not yet settled, counted against the limit
    last_stop: str | None = None  # why the latest attempt was not sent or was refused for credit; None once one is
    # Called with (role, usd, uncertain) for each settled attempt, under the lock; it must not raise.
    record: Callable[[str, float, bool], None] | None = field(default=None, repr=False, compare=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False, compare=False)

    def reserve(self, worst_case_usd: float) -> None:
        """Hold this attempt's worst case against the limit until settle() is called with it as `reserved`."""
        with self._lock:
            if self.overrun:
                self.last_stop = f"no request is sent after one that cost more than its worst case: {self.overrun}"
                raise BudgetExceeded(self.last_stop)
            if self.spent_usd + self.held_usd + worst_case_usd > self.limit_usd:
                held = f" and ${self.held_usd:.4f} held by requests in flight" if self.held_usd else ""
                self.last_stop = (
                    f"spent ${self.spent_usd:.4f}{held}; the next request could cost up to ${worst_case_usd:.4f}, "
                    f"over the limit of ${self.limit_usd:.2f}"
                )
                raise BudgetExceeded(self.last_stop)
            self.held_usd += worst_case_usd
            self.last_stop = None

    def refused_for_credit(self, reason: str) -> None:
        """The provider refused an attempt for lack of credit (OutOfCredit): recorded as the latest stop."""
        with self._lock:
            self.last_stop = reason

    def settle(self, role: str, usd: float, *, uncertain: bool = False, reserved: float | None = None) -> None:
        """Count an attempt that ended, and release what reserve() held for it (`reserved`)."""
        with self._lock:
            if reserved is not None:
                self.held_usd = max(0.0, self.held_usd - reserved)
                if usd > reserved:
                    self.overrun = f"an attempt cost ${usd:.6f}, more than the ${reserved:.6f} reserved for it"
            self.spent_usd += usd
            self.requests += 1
            if uncertain:
                self.uncertain_usd += usd
            self.by_role[role] = self.by_role.get(role, 0.0) + usd
            if self.record is not None:
                self.record(role, usd, uncertain)

    @property
    def left_usd(self) -> float:
        with self._lock:
            return max(0.0, self.limit_usd - self.spent_usd - self.held_usd)
