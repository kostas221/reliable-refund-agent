"""What the agent is told when people act outside the chat (plan section 5), and how it is told. Text only: it grants
nothing, and execute_refund still checks the database.

The first pilot showed why the wording matters. A notice that said only "approved by a staff member" left the agent
unsure whether the customer had confirmed, and once it asked the customer to confirm again instead of paying (D09).
A staff member decides only on a request the customer has confirmed, so the notice says both. A rejection's notice
also gives the staff member's reason, so the agent can pass it on (dialogue audit of 2026-10-18: without it the
customer learned only that the request was rejected).

A staff decision stores its notice in the same transaction (table agent_notices), and deliver_pending() hands the
stored notices to the agent. The customer's cancel button stores one too (review of the model comparison,
2026-10-24): in D28 the customer cancelled before the staff decision, and the agent, told nothing, asked the customer
to cancel with the button. That notice starts no run: the agent reads it at the customer's next message, since a run
with no customer message in front of it was filled with a new proposal (confirmation run of 2026-10-24). The server
calls deliver_pending() after a decision or a cancellation, when it starts and every few seconds, so a server that
stops between the decision and the agent's run loses nothing (outside review of 2026-10-15). The evaluation runner
calls it too, so it measures the product's path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Engine, text

from refund_agent.agent.costs import BudgetExceeded

if TYPE_CHECKING:
    from refund_agent.agent.graph import Agent

MAX_ATTEMPTS = 3  # a delivery that keeps failing stops here, so a failing model is not called without end

log = logging.getLogger("refund_agent.notices")


def staff_decision(proposal_id: str, decision: Literal["approved", "rejected"], reason: str | None = None) -> str:
    if decision == "approved":
        return (
            f"The customer confirmed request {proposal_id} and a staff member approved it, so it is ready to be paid."
        )
    rejected = f"The customer confirmed request {proposal_id}, but a staff member rejected it, so nothing will be paid."
    return f'{rejected} The staff member gave this reason for the customer: "{reason}"' if reason else rejected


def customer_cancelled(proposal_id: str, status: str) -> str:
    """The customer pressed cancel; a request that had already expired or stopped being valid was closed as such."""
    if status == "cancelled":
        return f"The customer cancelled request {proposal_id} with the button on its card, so nothing will be paid."
    return f"The customer pressed cancel on request {proposal_id}, which was already {status}, so nothing will be paid."


def notice_text(proposal_id: str, decision: str, reason: str | None, status: str) -> str:
    if decision == "cancelled":
        return customer_cancelled(proposal_id, status)
    return staff_decision(proposal_id, decision, reason)


def deliver_pending(
    engine: Engine, agent: Agent, clock: Callable[[], datetime], conversation_id: str | None = None
) -> int:
    """Tell the agent of the staff decisions it has not been told of yet, oldest first, in every conversation or in
    one. Returns how many were delivered. A notice is marked delivered only after the agent's run, and the agent
    ignores a notice ID it has already applied, so delivering twice is safe."""
    with engine.connect() as conn:
        pending = (
            conn.execute(
                text(
                    "SELECT n.id, n.conversation_id, n.proposal_id, n.decision, d.reason, p.status "
                    "FROM agent_notices n JOIN proposals p ON p.id = n.proposal_id "
                    "LEFT JOIN staff_decisions d ON d.proposal_id = n.proposal_id "
                    "WHERE n.delivered_at IS NULL AND n.attempts < :most "
                    "AND (CAST(:conversation AS text) IS NULL OR n.conversation_id = :conversation) "
                    "ORDER BY n.created_at, n.id"
                ),
                {"most": MAX_ATTEMPTS, "conversation": conversation_id},
            )
            .mappings()
            .all()
        )
    delivered = 0
    for notice in pending:
        try:
            event = notice_text(notice["proposal_id"], notice["decision"], notice["reason"], notice["status"])
            # A staff decision wakes the agent, which pays an approved request or passes on a rejection's reason; the
            # customer's cancellation is read at the customer's next message (confirmation run of 2026-10-24).
            wake = notice["decision"] != "cancelled"
            agent.notify(notice["conversation_id"], event, notice_id=notice["id"], wake=wake)
        except BudgetExceeded:
            raise  # a paid run's stop, not a failed delivery: the notice stays pending and the run ends
        except Exception as error:  # the decision stays stored; the notice is tried again later
            log.warning("notice %s not delivered: %s", notice["id"], error)
            _mark(engine, notice["id"], "attempts = attempts + 1, last_error = :error", error=str(error)[:500])
            continue
        _mark(engine, notice["id"], "attempts = attempts + 1, delivered_at = :now, last_error = NULL", now=clock())
        delivered += 1
    return delivered


def _mark(engine: Engine, notice_id: str, assignments: str, **values: object) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE agent_notices SET {assignments} WHERE id = :id AND delivered_at IS NULL"),
            {"id": notice_id, **values},
        )
