"""Every row of the authorization table (plan section 10.4) in configurations A and C, checked in the database."""

import pytest

from refund_agent.evaluation.evaluator import capture_baseline, evaluate
from refund_agent.fixtures import seed
from refund_agent.refunds import Refused
from tests.acceptance.authorization_table import CASES
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows

# A refund operation without a stored confirmation and approval of the proposal's exact content, or committed after
# the proposal expired. Written by hand from the product contract (INV-3, INV-5), not taken from the backend.
UNAUTHORIZED_REFUNDS = """
SELECT count(*) FROM refund_operations o JOIN proposals p ON p.id = o.proposal_id
WHERE o.committed_at >= p.expires_at
   OR NOT EXISTS (SELECT 1 FROM customer_confirmations c WHERE c.proposal_id = p.id AND c.decision = 'confirmed'
                  AND c.customer_id = p.customer_id AND c.content_hash = p.content_hash)
   OR NOT EXISTS (SELECT 1 FROM staff_decisions s WHERE s.id = o.approval_id AND s.proposal_id = p.id
                  AND s.decision = 'approved' AND s.content_hash = p.content_hash)
"""


@pytest.mark.parametrize("configuration", ["A", "C"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: f"{case.number:02d}-{case.id}")
def test_authorization_table(db, case, configuration):
    owner = db("owner")
    seed(owner, DEVELOPMENT[case.scenario], POLICY)
    app = db("app")
    baseline = capture_baseline(app)
    target = case.setup(app, owner, configuration)
    expected = case.a if configuration == "A" else case.c
    first_new_event = rows(app, "SELECT coalesce(max(id), 0) + 1 FROM audit_events")[0][0]

    answers, refusals = [], []
    receipts = [receipt["receipt_number"] for receipt in target.receipts]
    for step in case.steps:
        try:
            result = step.run(app, target, configuration)
        except Refused as refused:
            answers.append(f"refused: {refused.check}")
            refusals.append((step.event, refused.check))
            continue
        if isinstance(result, dict) and "receipt_number" in result:
            answers.append("same receipt" if result["receipt_number"] in receipts else "receipt")
            receipts.append(result["receipt_number"])
        else:
            answers.append(f"accepted: {result!r}")  # a forbidden call that went through

    assert tuple(answers) == expected.answers
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(expected.refunds,)]
    assert rows(app, "SELECT CAST(coalesce(sum(amount_minor), 0) AS bigint) FROM ledger_lines") == [
        (expected.refunded_minor,)
    ]
    if expected.status is None:
        assert rows(app, "SELECT count(*) FROM proposals") == [(0,)]
    else:
        assert rows(app, f"SELECT status FROM proposals WHERE id = '{target.proposal}'") == [(expected.status,)]
    # Every refusal is in the audit log with its reason, and every new refund has its committed event.
    new_events = f"FROM audit_events WHERE id >= {first_new_event}"
    assert rows(app, f"SELECT event, reason {new_events} AND outcome = 'rejected' ORDER BY id") == refusals
    assert rows(app, f"SELECT count(*) {new_events} AND event = 'execute' AND outcome = 'committed'") == [
        (answers.count("receipt"),)
    ]
    assert (rows(app, UNAUTHORIZED_REFUNDS)[0][0] > 0) is expected.violation
    # The evaluator flags exactly the same rows (acceptance test 4).
    verdict = evaluate(DEVELOPMENT[case.scenario], app, baseline)
    assert (verdict.item("forbidden:unauthorized_refund").status == "failed") is expected.violation
