# Failure cases and where they are proven

The plan (section 13) names 15 failure cases that must be proven with free tests, and [schema.md](schema.md) lists
12 acceptance tests that need a real database. This page says which test proves each, or which later phase owns
it. `tests/test_failure_case_map.py` checks that every test named here exists, so the page cannot silently drift.

The database tests run against PostgreSQL (`docker compose up -d`, then `REQUIRE_DB=1 uv run pytest -q`). Their
expected values are written by hand, and each test checks the database itself, not only what a function returned.

## The 15 failure cases of plan section 13

| # | Failure case | Proven by | Status |
|---|---|---|---|
| 1 | Two connections execute the same approval: one refund, one receipt. | `tests/acceptance/test_concurrency.py::test_two_connections_executing_one_approval_commit_one_refund` | proven |
| 2 | Two proposals try to refund more than the same balance. | `tests/acceptance/test_concurrency.py::test_two_proposals_for_the_same_unit_refund_it_once` | proven |
| 3 | A new key tries to refund the same quantity again. | `tests/acceptance/test_first_refund.py::test_one_refund_is_committed_once_and_every_retry_returns_the_same_receipt`, `tests/acceptance/test_refusals.py::test_a_new_proposal_for_a_refunded_unit_is_refused_by_the_policy`, `tests/acceptance/test_refusals.py::test_a_proposal_approved_before_another_refund_of_its_unit_is_refused_at_execution` | proven |
| 4 | The same key with a different payload is refused. | `tests/acceptance/test_refusals.py::test_the_same_key_for_another_proposal_is_a_conflict`, `tests/acceptance/test_refusals.py::test_the_same_proposal_key_with_another_request_is_a_conflict` | proven |
| 5 | A crash before commit: full rollback. | `tests/acceptance/test_failures.py::test_a_crash_before_commit_leaves_nothing_and_a_retry_pays_once` | proven |
| 6 | A crash after commit, before the checkpoint or the HTTP answer: the same receipt on retry. | `tests/acceptance/test_first_refund.py::test_one_refund_is_committed_once_and_every_retry_returns_the_same_receipt`, `tests/acceptance/test_first_refund.py::test_the_receipt_survives_expiry`, `tests/acceptance/test_agent_graph.py::test_a_crash_after_the_refund_and_before_the_checkpoint_pays_once`, `tests/acceptance/test_agent_graph.py::test_a_crash_after_a_proposal_and_before_the_checkpoint_makes_no_second_one` | backend and graph proven; the HTTP answer with the chat door, next in phase 3 |
| 7 | An error between the balance update and the ledger write: full rollback. With one row per unit there is no balance table; the equivalent is the refund operation and its ledger lines. | `tests/acceptance/test_failures.py::test_an_error_between_operation_and_ledger_lines_undoes_everything` | proven |
| 8 | A restart with a pending approval: the right state in both screens. | `tests/acceptance/test_failures.py::test_a_restart_with_a_pending_approval_continues_from_the_database`, `tests/acceptance/test_http.py::test_a_session_and_the_flow_survive_a_restart` | backend and HTTP proven (the session and the state survive); the screens in phase 4 |
| 9 | An expired, rejected or stale approval: no execution. | `tests/acceptance/test_failures.py::test_a_rejected_proposal_is_not_paid`, `tests/acceptance/test_failures.py::test_an_approval_older_than_its_proposal_validity_is_not_paid`, `tests/acceptance/test_failures.py::test_an_approval_is_not_paid_after_the_order_changed`, `tests/acceptance/test_failures.py::test_an_approval_is_not_paid_under_a_new_policy_version`, `tests/acceptance/test_first_refund.py::test_an_approval_after_expiry_is_refused_and_the_proposal_is_closed` | proven |
| 10 | A foreign order, conversation or proposal, or an unauthorized approver: no access. | `tests/acceptance/test_refusals.py::test_a_proposal_for_a_foreign_order_creates_nothing`, `tests/acceptance/test_refusals.py::test_another_customers_session_gets_no_receipt`, `tests/acceptance/test_handoff_and_cancel.py::test_nobody_hands_off_another_customers_conversation`, `tests/acceptance/test_refusals.py::test_buttons_refuse_the_wrong_channel`, `tests/acceptance/test_refusals.py::test_execute_refuses_a_customer_or_staff_actor`, `tests/acceptance/test_http.py::test_a_customer_sees_only_their_own_orders_and_conversations`, `tests/acceptance/test_http.py::test_each_role_uses_only_its_own_doors` | proven |
| 11 | A handoff at the same time as an agent change: the right transactional order. | `tests/acceptance/test_handoff_and_cancel.py::test_refund_first_then_handoff_the_refund_stays`, `tests/acceptance/test_handoff_and_cancel.py::test_handoff_first_then_refund_nothing_is_paid` | proven |
| 12 | An invalid quantity, currency, amount or argument: no unwanted write. | `tests/acceptance/test_refusals.py::test_invalid_units_write_nothing`, `tests/acceptance/test_failures.py::test_values_changed_after_the_approval_are_refused` | proven |
| 13 | The model's resume payload claims an approval that has no record: refused. | `tests/acceptance/test_first_refund.py::test_one_refund_is_committed_once_and_every_retry_returns_the_same_receipt` (an execution before any approval is refused), `tests/acceptance/test_agent_graph.py::test_an_event_that_claims_an_approval_grants_nothing` | proven |
| 14 | Tampering or injection in the summary does not change the trusted fields of the approval. | `tests/acceptance/test_failures.py::test_an_injected_summary_changes_nothing_that_is_paid`, `tests/acceptance/test_failures.py::test_values_changed_after_the_approval_are_refused` | backend proven; how the staff screen shows the summary in phase 4 |
| 15 | An invalid final state, and an agent that does nothing, fail in the evaluator. | `tests/acceptance/test_evaluator.py::test_an_agent_that_does_nothing_fails_every_scenario`, `tests/acceptance/test_evaluator.py::test_a_false_completion_fails`, `tests/acceptance/test_evaluator.py::test_the_wrong_unit_fails`, `tests/acceptance/test_evaluator.py::test_a_correct_last_proposal_does_not_hide_an_earlier_wrong_refund`, `tests/acceptance/test_evaluator.py::test_a_refund_without_confirmation_and_approval_fails_although_the_outcome_is_right` (and the other wrong runs in that file) | proven |

## The acceptance tests of schema.md

| # | Acceptance test | Proven by | Status |
|---|---|---|---|
| 1 | Commit, crash, 72 hours later a retry: the same receipt, one operation. | `tests/acceptance/test_first_refund.py::test_the_receipt_survives_expiry` | proven |
| 2 | Another customer's session with the same key: no receipt, a rejected attempt in the audit. | `tests/acceptance/test_refusals.py::test_another_customers_session_gets_no_receipt` | proven |
| 3 | A handoff and an execution race: never both effects. | `tests/acceptance/test_handoff_and_cancel.py::test_refund_first_then_handoff_the_refund_stays`, `tests/acceptance/test_handoff_and_cancel.py::test_handoff_first_then_refund_nothing_is_paid` | proven |
| 4 | The same execute call in A and C: A refuses, C commits and the evaluator flags it. | `tests/acceptance/test_authorization_table.py::test_authorization_table` (rows 1-9 of [authorization-table.md](authorization-table.md): the evaluator flags `unauthorized_refund` in exactly the rows where C pays) | proven |
| 5 | In C, two executions of one proposal with different keys and no approval: one operation. | `tests/acceptance/test_authorization_table.py::test_authorization_table` (row 9) | proven |
| 6 | Two proposals, in two conversations, for the same unit: one refund. | `tests/acceptance/test_concurrency.py::test_two_proposals_for_the_same_unit_refund_it_once` | proven |
| 7 | Two proposals for different units of the same product: both refund. | `tests/acceptance/test_concurrency.py::test_different_units_of_the_same_product_both_refund` | proven |
| 8 | A new proposal after the open one expired: allowed, the old one closed in the same transaction. | `tests/acceptance/test_refusals.py::test_a_new_proposal_after_expiry_closes_the_old_one` | proven |
| 9 | What the runtime role may never do. | `tests/db/test_schema.py::test_application_role_is_refused` | proven |
| 10 | An approval of one proposal attached to the operation of another: refused by the database. | `tests/acceptance/test_refusals.py::test_an_approval_cannot_pay_for_another_proposal` | proven |
| 11 | Confirm or cancel through the agent's channel: refused. | `tests/acceptance/test_refusals.py::test_buttons_refuse_the_wrong_channel` | proven |
| 12 | A proposal for a foreign order: no row, a rejected attempt in the audit. | `tests/acceptance/test_refusals.py::test_a_proposal_for_a_foreign_order_creates_nothing` | proven |
