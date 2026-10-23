"""The checks of 2026-10-23 replayed on the saved run of 2026-10-22 (refund_agent/evaluation/replay.py): they decide
what the review measured, with the production functions, and nothing else (plan change log, 2026-10-23)."""

from refund_agent.evaluation.replay import replay
from refund_agent.policy import REPO_ROOT

RUN = REPO_ROOT / "runs" / "pilot-20261022T165428Z-gpt-6-luna-none"


def test_the_checks_stop_the_nine_clarification_failures_of_the_last_run_and_nothing_else():
    found = replay([RUN])
    # D09, D17 and D31 proposed without asking; D33 asked with a call and proposed before the answer.
    tries = sorted({" ".join(line.split()[1:3]) for line in found.refused})
    assert tries == [
        "D09 try1",
        "D09 try2",
        "D17 try1",
        "D17 try2",
        "D31 try1",
        "D31 try2",
        "D31 try3",
        "D33 try1",
        "D33 try3",
    ]
    assert (len(found.refused), found.proposals) == (9, 91)
    assert [line.split(":")[0].split()[1:3] for line in found.held] == [
        ["D33", "try1"],
        ["D33", "try2"],
        ["D33", "try3"],
    ]
    assert (found.answers_with_calls, found.agent_answers) == (3, 706)
    # D37 try 3: the customer's yes to "Would you like me to ask a staff member to help?" is now a request.
    assert found.changed == [f"{RUN.name} D37 try3: accepted 'Yes, please.'"]
    assert found.handoffs == 29
