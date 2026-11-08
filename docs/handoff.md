# Handing a conversation to a person

For the staff member and the observer of the local trial, and for a reviewer checking section 4 of the release brief
([release-brief-2026-10-31.md](release-brief-2026-10-31.md)).

A handoff ends the assistant's part of a conversation. A staff member takes the case in the console and continues
with the customer **by email, outside the application**. Taking a case is not resolving it: v1 has no place in the
application to record how a handed-off case ended, and no way to pay a refund for it from the console.

## What starts a handoff

| Start | Recorded origin | What the backend checks |
|---|---|---|
| The customer presses **Talk to a person**, then **Yes, talk to a person** | `customer` | The customer owns the conversation |
| The customer asks for a person in the chat, and the assistant hands off | `customer`, "according to the assistant" in the console | The customer's latest message names a person or says yes to the assistant's offer of one (`tests/test_request_for_person.py`) |
| A case the policy gives to staff (units sent but not received, a delivered order that never arrived, a request to refund shipping) | `agent` | The order's status, the disputed units and the conversation's latest decision (`refunds.refer_to_staff`); for units the customer says were sent, that a customer message says so, or says yes to the agent's question whether they were (`refunds.claim_of_sending`) |
| A staff member presses **Take over** on a conversation | `staff`, taken at once | The actor is staff |

In every case the conversation becomes `human_controlled` in one transaction: its open requests are closed with
"Handed to a person" and nothing is paid for them, and every later write by the assistant is refused
([product-contract.md](product-contract.md), INV-8).

## What each side sees

The customer:

- Before choosing: "A staff member takes over this conversation and writes to you by email, at the address of your
  account. Any request still open here is closed, and nothing is paid for it; the staff member decides what happens
  next."
- While nobody has taken the case: **Waiting for a staff member.** A staff member will write to you by email, at the
  address of your account; their replies do not come through this chat. The assistant makes no more changes here.
  You can still write: your messages are kept for the staff member.
- Once a staff member has taken it: **A staff member has taken your case.** They will write to you by email, at the
  address of your account; their replies do not come through this chat. The assistant makes no more changes here.
  You can still write: your messages are kept for the staff member.
- The closed request's card: "Handed to a person. Nothing will be paid for this request."

The staff member:

- The queue's **Handed to a person (N)**: how the case started, the customer's ID, the handoff's ID and time.
- The case: its origin, the reason, the request it closed, the earlier actions, the messages (including those written
  after the handoff), the history, and, checked by the backend, the customer's name and email. **Take this case**
  records it as taken by them; it leaves the queue, and the history shows "Case taken".

## How a staff member continues the case

1. Take the case, so that no other staff member answers the same customer.
2. Read the messages, including any the customer wrote after the handoff; the assistant answered none of them.
3. Write to the customer at the email shown beside their name: what was decided, or what is still needed from them.
4. If a refund is due, it is paid through the shop's own process, outside this application (a v1 limit).
5. To come back to a taken case, keep its address: the console's address names the open case
   (`#conversation=...&handoff=...`). There is no list of taken cases.

### In the local trial

The accounts are fictional (`@example.test`) and no email is sent. The participant who plays the staff member writes
the email as plain text on the observation form, and the observer gives it to the customer participant only after
asking what they expect to happen next. No money moves.

## What is checked, and where

The four situations of the release brief's section 4, and the three things it asks to verify. The tests run in mock
mode with the scripted agent; the paid development runs are the model's evidence.

| Situation | Tests |
|---|---|
| The customer asks for a person, by the button | `tests/browser/test_screens.py::test_a_case_handed_to_a_person_through_both_screens_and_a_restart`; `tests/acceptance/test_http.py::test_a_customer_can_cancel_and_ask_for_a_person`; `tests/acceptance/test_handoff_and_cancel.py::test_handoff_stops_the_agent_and_withdraws_the_open_proposal` |
| The customer asks for a person, in the chat | `tests/test_request_for_person.py`; `tests/acceptance/test_agent_tools.py::test_a_request_for_a_person_needs_words_the_customer_wrote`, `::test_a_request_for_a_person_names_one_or_answers_an_offer_of_one` |
| A case the policy gives to staff | `tests/acceptance/test_agent_tools.py::test_a_handoff_that_names_a_case_for_staff_records_the_request_and_hands_off`, `::test_a_handoff_for_staff_names_the_customers_order_and_its_units`; `tests/acceptance/test_mock_runs.py::test_a_case_for_staff_named_in_the_handoff_passes_without_a_proposal_first`; a return dispute on the customer's words: `tests/test_claim_of_sending.py`, `tests/acceptance/test_agent_tools.py::test_a_return_dispute_rests_on_the_customers_words_that_the_units_were_sent`. With the model: 60 of 60 required handoffs in the instructions-v12 run on 128 development scenarios ([pilot/results.md](pilot/results.md)) |
| A staff decision whose delivery to the assistant keeps failing | `tests/acceptance/test_agent_notices.py::test_a_delivery_that_keeps_failing_stops_after_three_attempts` (then shown to staff under "Decisions the assistant has not been told of"), `::test_a_notice_whose_run_failed_is_finished_by_the_next_delivery`, `::test_a_notice_delivered_twice_is_applied_once`; `tests/acceptance/test_live_mode.py::test_a_decision_whose_delivery_failed_three_times_gets_new_attempts_at_a_restart` |
| A restart with a decision pending | `tests/browser/test_screens.py::test_a_restart_with_a_pending_approval_leaves_both_screens_right`; `tests/acceptance/test_failures.py::test_a_restart_with_a_pending_approval_continues_from_the_database`; `tests/acceptance/test_agent_notices.py::test_a_notice_stored_before_the_server_stopped_is_delivered_after_it_starts_again` |
| A restart with a handoff pending | `tests/browser/test_screens.py::test_a_case_handed_to_a_person_through_both_screens_and_a_restart` |

| To verify | Tests |
|---|---|
| The customer is told what waits and how the reply comes | `frontend/src/status.test.ts` ("what a customer reads while a person has the conversation"); the browser test above, before and after the restart and after the case is taken |
| Staff can identify and take the case | `tests/acceptance/test_http.py::test_staff_have_the_contact_of_a_customer_a_person_now_serves`; `tests/acceptance/test_handoff_and_cancel.py::test_staff_take_an_open_handoff_once`; the browser test above |
| The assistant cannot continue after the takeover | `tests/acceptance/test_agent_tools.py::test_after_a_handoff_the_agent_changes_nothing`, `::test_an_approved_request_is_not_paid_after_a_handoff`; `tests/acceptance/test_handoff_and_cancel.py::test_handoff_first_then_refund_nothing_is_paid`; `tests/acceptance/test_agent_graph.py::test_after_a_handoff_the_model_is_not_asked_again`; `tests/acceptance/test_agent_notices.py::test_no_notice_wakes_a_conversation_a_person_took_over`; `tests/acceptance/test_http_chat.py::test_after_a_handoff_the_chat_door_records_without_answering`; the browser test above (a message after the takeover is stored and unanswered, no refund) |

## Limits

- Whether customers understand the waiting text is not something a test can show; the five-person trial observes it
  (release brief, section 5).
- No list of taken cases: a taken case is found again only by its address.
- No staff reply in the chat, no record in the application of how a case ended, and no refund from the console for a
  handed-off conversation.
- No email is sent by the application; the address is the one the shop holds for the account.
- v1.2's held-out and stress sets require no handoff. The comparison set of v1.3 required 18, and both models made
  all 18 ([held-out-v1.3/results.md](held-out-v1.3/results.md)); those results check the assistant's handoff, not
  what the customer and the staff member do after it.
