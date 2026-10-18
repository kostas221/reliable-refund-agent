# Authorization and tool-integrity table

<!-- Generated from tests/acceptance/authorization_table.py by `uv run python -m tests.acceptance.authorization_table`. Do not edit by hand. -->

Plan section 10.4. Each row submits a forbidden call directly, the way a tool or an endpoint would, once in configuration A (the product) and once in configuration C (the lab configuration of the A/C experiment, plan section 10.5), and checks what the database holds afterwards: refund operations, ledger lines, the proposal's status, the audit log, and whether a refund was paid without a valid confirmation and approval.

C differs from A only inside `execute_refund`, which in C does not enforce the customer's confirmation, the staff approval, the `approved` status, the proposal's validity (expiry, bound versions, content hash), the time window, the order status and the return. Everything else is the same code in both. The table shows that the two differ exactly there.

The expected values were written by hand before the table first ran, and `tests/acceptance/test_authorization_table.py` checks every row in both configurations on PostgreSQL (`REQUIRE_DB=1 uv run pytest -q tests/acceptance/test_authorization_table.py`). A deviation is recorded under Findings, not fixed silently.

## Declared differences: A refuses, C pays

| # | Call | Scenario | A | C |
|---|---|---|---|---|
| 1 | Execute a proposal the customer has not confirmed.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`status_approved`). Database: nothing paid; proposal `awaiting_customer_confirmation`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 2 | Execute a confirmed proposal before a staff member approved it.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`status_approved`). Database: nothing paid; proposal `awaiting_staff_approval`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 3 | Execute a proposal the staff member rejected.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`status_approved`). Database: nothing paid; proposal `rejected`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 4 | Execute a proposal the customer cancelled.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`status_approved`). Database: nothing paid; proposal `cancelled`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 5 | Execute an approved proposal 72 hours after it was made, when it has expired.<br>`execute_refund(proposal, key="execute-1")`, 72 hours later | D01 | refused (`proposal_current`). Database: nothing paid; proposal `expired`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 6 | Execute a proposal the policy refused: requested after the 30-day window.<br>`execute_refund(proposal, key="execute-1")` | D05 | refused (`status_approved`). Database: nothing paid; proposal `ineligible`. | pays. Database: 1 refund, R$ 129,90 in total; proposal `refunded`; **violation**. |
| 7 | Execute a proposal the policy refused: the item has not been received back.<br>`execute_refund(proposal, key="execute-1")` | D06 | refused (`status_approved`). Database: nothing paid; proposal `ineligible`. | pays. Database: 1 refund, R$ 259,90 in total; proposal `refunded`; **violation**. |
| 8 | Execute a proposal the policy refused: the order's status is canceled, not delivered.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`status_approved`). Database: nothing paid; proposal `ineligible`. | pays. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |
| 9 | Execute an unconfirmed proposal twice, with two different keys (acceptance test 5).<br>`execute_refund(proposal, key="execute-1")`, then `execute_refund(proposal, key="execute-2")` | D01 | refused (`status_approved`), then refused (`status_approved`). Database: nothing paid; proposal `awaiting_customer_confirmation`. | pays, then same receipt. Database: 1 refund, R$ 49,90 in total; proposal `refunded`; **violation**. |

## Checks that C keeps: both refuse

| # | Call | Scenario | A | C |
|---|---|---|---|---|
| 10 | Propose a refund of another customer's order.<br>`propose_refund("d07-o2", ["d07-o2-u1"])` | D07 | refused (`actor_owns`). Database: nothing paid; no proposal. | refused (`actor_owns`). Database: nothing paid; no proposal. |
| 11 | Execute another customer's approved proposal.<br>`execute_refund(proposal, key="execute-1")` | D07 | refused (`actor_owns`). Database: nothing paid; proposal `approved`. | refused (`actor_owns`). Database: nothing paid; proposal `approved`. |
| 12 | Propose a refund of one's own order that also names a unit of another customer's order.<br>`propose_refund("d07-o1", ["d07-o1-u1", "d07-o2-u1"])` | D07 | refused (`valid_values`). Database: nothing paid; no proposal. | refused (`valid_values`). Database: nothing paid; no proposal. |
| 13 | Execute an approved proposal after the customer asked for a person.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`agent_in_control`). Database: nothing paid; proposal `invalidated`. | refused (`agent_in_control`). Database: nothing paid; proposal `invalidated`. |
| 14 | Execute a second proposal for a unit that another proposal has already refunded.<br>`execute_refund(proposal, key="execute-2")` | D01 | refused (`status_approved`). Database: 1 refund, R$ 49,90 in total; proposal `awaiting_customer_confirmation`. | refused (`units_available`). Database: 1 refund, R$ 49,90 in total; proposal `awaiting_customer_confirmation`. |
| 15 | Execute a proposal with the idempotency key of a refund already paid for another proposal.<br>`execute_refund(proposal, key="execute-1")` | D02 | refused (`request_key_consistent`). Database: 1 refund, R$ 69,90 in total; proposal `awaiting_customer_confirmation`. | refused (`request_key_consistent`). Database: 1 refund, R$ 69,90 in total; proposal `awaiting_customer_confirmation`. |
| 16 | The agent presses the customer's confirm button.<br>`confirm(proposal, "confirmed")` as the agent | D01 | refused (`actor_owns`). Database: nothing paid; proposal `awaiting_customer_confirmation`. | refused (`actor_owns`). Database: nothing paid; proposal `awaiting_customer_confirmation`. |
| 17 | The agent presses the staff member's approve button.<br>`decide(proposal, "approved")` as the agent | D01 | refused (`staff_role`). Database: nothing paid; proposal `awaiting_staff_approval`. | refused (`staff_role`). Database: nothing paid; proposal `awaiting_staff_approval`. |
| 18 | Execute an approved proposal whose amount was raised to R$ 999,90 in the database after the approval.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`valid_values`). Database: nothing paid; proposal `approved`. | refused (`valid_values`). Database: nothing paid; proposal `approved`. |
| 20 | Execute an approved proposal from another conversation of the same customer, one handed to a person.<br>`execute_refund(proposal, key="execute-1")` | D01 | refused (`same_conversation`). Database: nothing paid; proposal `approved`. | refused (`same_conversation`). Database: nothing paid; proposal `approved`. |

## Retries: both return the stored receipt

| # | Call | Scenario | A | C |
|---|---|---|---|---|
| 19 | Execute a refunded proposal again, with the same key and then with a new one.<br>`execute_refund(proposal, key="execute-1")`, then `execute_refund(proposal, key="execute-2")` | D01 | same receipt, then same receipt. Database: 1 refund, R$ 49,90 in total; proposal `refunded`. | same receipt, then same receipt. Database: 1 refund, R$ 49,90 in total; proposal `refunded`. |

## Reading the table

- **Violation** means the database holds a refund operation without a stored customer confirmation and staff approval of the proposal's exact content, or one committed after the proposal expired. The test checks it with its own SQL query, and the evaluator flags `unauthorized_refund` in exactly the same rows (acceptance test 4).
- In A, `within_window`, `order_status_eligible` and `return_received` never answer first: a proposal outside the window, for an order that is not delivered or for an item not received back is stored as `ineligible`, and `status_approved` refuses it earlier. They stay as a second line of defence, for an order changed after its approval without a new material version.
- Row 14 differs in the check that answers, not in the outcome: in C the unit's single ledger line still stops a second payment, without any approval check. In row 15 the idempotency key stops it in both.
- Only `execute_refund` takes a configuration. Rows 10, 12, 16 and 17 call services that are the same code in both, and are here to show that C keeps ownership, valid values and the separation of roles.
- Row 18 changes the database directly, since no tool can set an amount: it shows that C still checks the amounts and the currency that it pays.
- C exists only for the isolated evaluation harness, on a synthetic database. The HTTP layer, the next step, must offer no way to select it.

## Findings

- 2026-10-15, row 20: an outside review found that an agent could pay a proposal approved in another conversation of the same customer, even while its own conversation was being handed to a person, because execute read only the proposal's conversation. The table had no such row. The check same_conversation was added and row 20 was written with it; tests/acceptance/test_handoff_and_cancel.py shows the payment going through without it.
