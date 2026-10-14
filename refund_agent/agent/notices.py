"""What the agent is told when people act outside the chat (plan section 5). Text only: it grants nothing, and
execute_refund still checks the database.

The first pilot showed why the wording matters. A notice that said only "approved by a staff member" left the agent
unsure whether the customer had confirmed, and once it asked the customer to confirm again instead of paying (D09).
A staff member decides only on a request the customer has confirmed, so the notice says both.
"""

from __future__ import annotations

from typing import Literal


def staff_decision(proposal_id: str, decision: Literal["approved", "rejected"]) -> str:
    if decision == "approved":
        return (
            f"The customer confirmed request {proposal_id} and a staff member approved it, so it is ready to be paid."
        )
    return f"The customer confirmed request {proposal_id}, but a staff member rejected it, so nothing will be paid."
