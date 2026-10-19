# The screens

The customer screen and the staff console (plan sections 7 and 8, phase 4), in `frontend/`: React and TypeScript,
built with Vite. They call only the doors of [http-api.md](http-api.md) and decide nothing. Every state they show is
read from the backend, and read again every few seconds.

## Run them in mock mode, without an API key

```bash
docker compose up -d
uv run python -m refund_agent.api
```

In a second terminal:

```bash
cd frontend && npm ci && npm run dev
```

Then open http://localhost:5173. The server loads scenario D01 (Ana's mug); `--scenario D04` loads another development
scenario, and `--keep` serves the previous run's database instead of a new one, to show a restart. It prints the
scenario's customer and staff member; the demo password is in `refund_agent/api/__main__.py`. In development the page
and the API share one origin through Vite's proxy, so the session cookie stays HttpOnly and SameSite=Strict. One
browser holds one session: to see both screens at once, use a second browser or a private window.

## The customer screen

- **Orders**: each unit with what was paid for it and whether it was returned or refunded, and the requests already
  made for the order, the same list the agent reads.
- **Choosing units** fills the chat with a first message that names them, which the customer can change. There is no
  other way to the agent: the choice becomes text through the chat door.
- **The chat**, with each proposal card placed after the agent's message of the turn that made it. While the agent
  answers, the customer's own text shows as "sending"; nothing else is shown before the backend has it.
- **The card**: the units and amounts the backend computed (none for a request the policy refused), the state in
  words, the policy citations behind a refusal, the validity, and the receipt once paid. Confirm and Decline appear
  while the backend waits for the customer and the validity has not passed; Cancel once confirmed, until paid.
- **Talk to a person**, after a second press. Once a person handles the conversation, the screen says so, and
  messages are still recorded for them.

## The staff console

- **The queue**: requests waiting for approval (amount, customer, expiry) and cases handed to a person. Since 2026-10-19 also any staff decision the assistant has not been told of after a failed delivery, with the attempts and the last error, until a delivery succeeds; after the last attempt it stays there for a person to take over (review of 2026-10-19, R1).
- **A request**: "Checked by the backend" (customer, order, units, amounts, state, when the customer confirmed, policy
  version) in one box, and "Not verified" text in another, dashed and labelled with its writer: the assistant's
  summary and the seller's message, as plain text. The approve button names the amount the backend computed.
- **A conversation**: its messages (not verified), its cards, and its history (the audit events: who did what, done
  or refused and why, with only values the backend set). Take over, after a second press.
- **A case handed to a person**: the origin, marked "according to the assistant" when the assistant recorded that the
  customer asked; the request it closed; the earlier actions; the model's texts, not verified; Take this case.

## Rules the screens keep

1. **Nothing says money was refunded before a receipt exists** (INV-10). "Refunded" needs the receipt; an approved
   request reads "Approved, not paid yet".
2. **A state is written in words**; colour only repeats it.
3. **Text nobody verified is plain text**, never markup (there is no `dangerouslySetInnerHTML` in `frontend/src`),
   labelled with its writer and kept apart from the backend's fields.
4. **The backend is read again** every 2.5 to 4 seconds. A failed read keeps the last answer on screen and says so;
   a page that loads while the server is down asks again every 3 seconds until it answers.
5. **A lost or uncertain answer claims nothing.** No answer, or a gateway that could not reach the backend, reads as
   "nothing is assumed", and the screen shows what is stored once the backend answers. A button pressed on a card
   that changed in the meantime gets the backend's refusal, and the card is read again.
6. **A change carries the session's CSRF token.** A page that lost it reads it again from its own session and tries
   once more; any other refusal is final.
7. **Signing out ends the session in the backend** before the page says so, and forgets what the page had open.

## Proven by

- `frontend/src/*.test.ts` (`npm test`, 44 tests): the words for every state and both viewers, never "Refunded"
  without a receipt, when each button shows, the money format, where a card goes among the messages, what each error
  answer means, and the CSRF retry (once, never a loop).
- `tests/acceptance/test_http.py` and `tests/acceptance/test_agent_tools.py`: the reads the screens use (requests per
  order, citations, the customer's conversations, the staff history without the model's words), on PostgreSQL.
- `tests/browser/test_screens.py`, in a real browser (the installed Chrome, through Playwright), typed and clicked,
  each person in a session of their own, what the screens show checked against the database:
  - a refund through both screens, to the receipt on the card;
  - a restart while the request waits for approval (failure case 8): the screens keep what they last read and say
    the server does not answer, then show the same state with no new sign-in, also after a reload, and the
    approval pays once;
  - a confirmation whose answer is lost on the way back (an uncertain HTTP result): the page says it does not know,
    then shows the stored state; Confirm pressed again in a second, stale tab is refused ("This changed in the
    meantime"), one confirmation stays, and the approval pays once;
  - a rejection (added 2026-10-19): the Reject button stays disabled until the staff member writes a reason for the
    customer, and the customer's card then shows "Rejected" with that reason, stored with the decision; no refund.

  The tests build the screens first and serve them with the API from one test server, on a copy of the template
  database, with the scripted agent: `REQUIRE_DB=1 uv run pytest tests/browser` (about a minute). Ten bugs planted
  one at a time were each caught on 2026-10-18: Confirm sending a decline, Approve rejecting, a decision storing no
  notice for the agent, changes without the CSRF token, another amount on the receipt, a restart signing everybody
  out, a failed read clearing the screen, a failed read not being told, a change whose answer is lost being sent
  again blindly, and a second confirmation not checked by the service. An eleventh, removing only the decision
  door's immediate delivery, changes nothing a person sees, since the server also delivers stored notices every few
  seconds.
- By hand on 2026-10-14, in the in-app browser against the demo server and its scripted agent, each checked in the
  database as well:

| Scenario | What was done | What the screens and the database showed |
|---|---|---|
| D01 | Choose the mug, send, confirm; the staff member approves | Card after the agent's message; "Waiting for staff approval"; then "Refunded, receipt R-00000001" in both screens; one operation of R$ 49,90 |
| D01 | Confirm stored, then the stale Confirm button pressed (an answer lost) | One confirmation; the second attempt refused in the audit log; the card read again |
| D01 | A request waiting for approval; the server stopped and started with `--keep` | While down, the last state with a notice; after, the same state in both screens, still signed in; approval gave the receipt |
| D08 | The seller's message claims a manager approved R$ 184,80 | 184,80 only in the seller's "Not verified" box; the approve button and the payment R$ 159,90 |
| D04 | The staff member rejects | "Rejected" in both screens, the agent tells the customer; no operation. Since 2026-10-19 a rejection also needs a reason, shown on the card (browser test) |
| D05 | A late request, then "I want a person"; then a new conversation and the button | Refusal with "Time limit `refund-policy/v1/window`" and no amount; the agent's handoff; a later message recorded, unanswered; the console tells the assistant's record from the button's |
| D08 | A case taken; a conversation taken over | Queue emptied; "handled by a person"; the history shows the staff member's handoff |

## Limits

- Overlapping reads of one screen (the timer's and one after a button) keep only the newest answer, so an older one arriving last cannot step the screen back (review of 2026-10-19, R8; `frontend/src/polling.test.ts`). The list of untold decisions is not covered by a browser test; its read is tested in `tests/acceptance/test_agent_notices.py`.

- The checks by hand drove the page with scripts inside it, because the browser pane was not displayed: forms were
  submitted and buttons clicked by code, so the keyboard and the mouse were not tested. Since 2026-10-18 the browser
  tests type and click the refund, the restart, a lost answer and a rejection with its reason; expired cards stay
  unit tests. The ten planted bugs above were run before the rejection test existed.
- An expired card was not seen live (it needs 72 hours of demo time). Its words and its missing confirm button are
  unit tests, and the backend's display of expiry is tested in `test_http.py`.
- The queue's list does not mark a handoff the assistant recorded on the customer's behalf; the case itself does.
- There is no chat between staff and customer (out of v1): after taking a case, the staff member acts elsewhere.
- Changes appear within a few seconds, by polling, not at once.
- The components themselves (`CustomerScreen.tsx`, `StaffScreen.tsx`) have no unit tests; their rules live in
  `status.ts`, `timeline.ts` and `api.ts`, which do.
- The screens are not yet in Docker Compose (phase 7).
