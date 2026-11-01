"""The live-model mode of the local server: what a paid session may spend, and how it stops (closing plan of
2026-10-31, section 3; outside critique of 2026-11-01).

For the project owner, who starts every paid session, and for anyone checking what one can spend. The default server
plays a fixed script and needs no key (mock mode). Started with --live, it serves the evaluated agent instead: the
same backend, tools, approvals and database, with the model behind OpenAIResponses.

- One budget for the whole server. The calls a customer's message starts and the calls a staff decision starts from
  the background draw on one Budget, whose lock holds each attempt's worst case until the attempt is settled, so two
  calls in flight cannot pass the limit together.
- What was spent is kept in the database. Each settled attempt is a row of model_spend (migration 0010). A server
  started again on the same database (--keep) adds the rows up first, so a restart never resets the count; a new
  database starts from zero, and the server says which when it starts.
- A stop is a pause. When the budget or the provider's credit stops a call, nothing stored is lost: the customer's
  message, the proposal cards and every staff decision stay as they are, and the screens say the agent is paused.
  The owner resumes by starting the server again on the same database with a larger budget (or after adding
  credit): pending staff decisions are delivered when it starts, and a run the stop cut short is finished at the
  customer's next message.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from refund_agent.agent.costs import Budget
from refund_agent.agent.notices import MAX_ATTEMPTS

log = logging.getLogger("refund_agent.live")

# The most one paid session may be given: the pilot's limit (plan section 12).
MOST_USD = 5.0


def spent_before(engine: Engine) -> dict[str, float]:
    """What the model attempts recorded in this database cost, by role, and the uncertain part of it."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT role, coalesce(sum(usd), 0), coalesce(sum(usd) FILTER (WHERE uncertain), 0) "
                "FROM model_spend GROUP BY role"
            )
        ).all()
    spent = {role: float(usd) for role, usd, _ in rows}
    spent["uncertain"] = sum(float(uncertain) for _, _, uncertain in rows)
    return spent


def recorder(engine: Engine, wall_clock: Callable[[], datetime] | None = None) -> Callable[[str, float, bool], None]:
    """Write each settled attempt to model_spend. A failed write is logged, never raised: the attempt was billed
    whatever happens here, and the budget in memory still counts it."""
    now = wall_clock or (lambda: datetime.now(UTC))

    def record(role: str, usd: float, uncertain: bool) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO model_spend (id, at, role, usd, uncertain) "
                        "VALUES (:id, :at, :role, :usd, :uncertain)"
                    ),
                    {"id": uuid.uuid4().hex, "at": now(), "role": role, "usd": usd, "uncertain": uncertain},
                )
        except Exception:
            log.exception("an attempt's cost ($%.6f) could not be written to model_spend", usd)

    return record


def session_budget(engine: Engine, limit_usd: float) -> Budget:
    """The server's one budget: the limit given at start, with what this database already recorded counted first."""
    if not 0 < limit_usd <= MOST_USD:
        raise ValueError(f"the budget must be above 0 and at most ${MOST_USD:.2f}")
    before = spent_before(engine)
    uncertain = before.pop("uncertain")
    return Budget(
        limit_usd,
        spent_usd=sum(before.values()),
        uncertain_usd=uncertain,
        by_role=before,
        record=recorder(engine),
    )


def retry_stuck_notices(engine: Engine) -> int:
    """Give the staff decisions whose delivery to the agent failed MAX_ATTEMPTS times new attempts. Called when the
    owner starts the server again on the same database: a provider that failed for a minute must not leave an
    approved refund unpaid for good. Returns how many."""
    with engine.begin() as conn:
        return conn.execute(
            text("UPDATE agent_notices SET attempts = 0 WHERE delivered_at IS NULL AND attempts >= :most"),
            {"most": MAX_ATTEMPTS},
        ).rowcount
