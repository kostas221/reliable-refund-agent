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


LATEST = REPO_ROOT / "runs" / "pilot-20261023T144102Z-gpt-6-luna-none"


def test_the_checks_of_the_review_after_the_selection_check_on_the_run_it_read():
    found = replay([LATEST])
    # The repaired selection check refuses exactly the proposals the run's own check refused, one per conversation.
    assert (len(found.refused), found.proposals) == (9, 95)
    assert sorted(line.split()[1] for line in found.refused) == ["D09"] * 3 + ["D17"] * 2 + ["D31"] * 3 + ["D33"]
    # Every shipping handoff of the run (D39 and D40, three each) had no words of the customer's: each now gets the
    # refusal that tells the agent how to read a question about shipping.
    assert found.shipping == 6 and len(found.shipping_changed) == 6
    assert {line.split()[1] for line in found.shipping_changed} == {"D39", "D40"}
    assert (found.changed, found.handoffs) == ([], 28)


STEP_C = REPO_ROOT / "runs" / "pilot-20261027T144002Z-gpt-6-luna-none"


def test_fact_lines_left_out_of_the_yes_check_change_one_decision_of_the_v1_2_confirmation():
    # Review of 2026-10-28: in D40 try 2 the fact line followed the offer, and the customer's genuine yes was refused.
    # With fact lines left out, that yes is accepted; nothing else changes, and the run's four fact lines stay.
    found = replay([STEP_C])
    assert found.shipping_changed == [
        f"{STEP_C.name} D40 try2: accepted 'Yes, please have a staff member review the R$18 shipping charge.'"
    ]
    assert (found.changed, found.handoffs, found.shipping) == ([], 35, 16)
    assert (len(found.refused), found.proposals) == (10, 137)
    assert sorted(line.split(":")[0].split()[1] for line in found.fact_lines) == ["D20", "D40", "D40", "D62"]


COMPARISON = [
    REPO_ROOT / "runs" / name
    for name in ("pilot-20261023T185612Z-gpt-6-luna-none", "pilot-20261023T201842Z-gpt-6.1-sol-low")
]


def test_a_shipping_handoff_rests_on_a_yes_to_the_offer_in_the_runs_of_the_model_comparison():
    found = replay(COMPARISON)
    # Review of the model comparison, 2026-10-24: every shipping handoff of both runs quoted the customer's first
    # words, and each was accepted at the time. Each is now refused: D39's question (Luna, three tries) is answered
    # from the policy, and D40's request (three tries of each) gets the offer of a staff member first.
    assert found.shipping == 9
    assert sorted(" ".join(line.split()[1:3]).rstrip(":") for line in found.shipping_changed) == sorted(
        [f"D39 try{n}" for n in (1, 2, 3)] + [f"D40 try{n}" for n in (1, 2, 3)] * 2
    )
    assert all(": refused " in line for line in found.shipping_changed)
    # Nothing else is decided differently: the same 10 selection refusals as the run's own, no person request changed.
    assert (len(found.refused), found.changed) == (10, [])


def test_the_fact_line_falls_on_the_missed_citations_of_the_model_comparison_and_on_few_others():
    found = replay(COMPARISON)
    where = sorted(" ".join(line.split(":")[0].split()[1:3]) for line in found.fact_lines)
    # The three citations Luna missed (D20 tries 1 and 2, D35 try 2) and Sol's one (D35 try 2), plus five answers that
    # state a fact the line is true of: D40's earlier refund (Luna) and D15's shipped controller (Sol, which cited the
    # exceptions section).
    assert where == sorted(
        ["D20 try1", "D20 try2", "D35 try2", "D40 try1", "D40 try2"] + ["D15 try1", "D15 try2", "D15 try3", "D35 try2"]
    )
