# HTTP layer

The doors of the customer screen and the staff console (plan sections 5, 7 and 8), in `refund_agent/api/`; the
screens call them.

Run it locally with `uv run python -m refund_agent.api` (the database must be up: `docker compose up -d`). It
recreates the database `refund_demo_api` with scenario D01 (Ana's mug), or another development scenario given with
`--scenario D04`, a demo password for its fictional users (in `refund_agent/api/__main__.py`), and serves the API
documentation, where every door can be tried, at http://localhost:8000/docs. With `--keep` it serves the previous
run's database as it is, with the business clock going on from its last event, to show that a restart loses nothing.
The screens that call these doors are described in [screens.md](screens.md).

## Who acts

The backend takes the actor from the session and from the door, never from a request body (plan section 6):

1. **Sign-in** (`POST /api/session`) checks the email and the password against an argon2 hash. A wrong email and a
   wrong password get the same answer, after the same work, so the answer does not reveal which emails exist.
2. **The session** is a random token in a cookie that is HttpOnly (JavaScript cannot read it), SameSite=Strict (no
   other site's page can make the browser send it) and Secure (HTTPS only; the local demo over plain HTTP is the
   one exception). The `sessions` table keeps only the token's SHA-256, the user, a CSRF token and the expiry: a
   session survives a restart, a sign-out ends it for good, and it expires after 8 hours of real time.
3. **Every change** (POST, DELETE) except signing in needs the session's CSRF token in the `X-CSRF-Token` header,
   which a page of another site cannot know (synchronizer token).
4. **Each door belongs to one role.** A customer's door acts as that customer; a console door acts as that staff
   member. A signed-in user of the other role gets 403, and the role is read from the database on every request.

## The doors

| Door | Who | Body | What it does |
|---|---|---|---|
| `POST /api/session`, `GET /api/session`, `DELETE /api/session` | anyone, then the signed-in user | `email`, `password` (sign-in only) | Sign in, read the session (with its CSRF token), sign out |
| `GET /api/orders` | customer | - | The customer's orders with each unit (product, paid amount, received back, refunded) and the requests already made for each order, the same list the agent reads |
| `GET /api/conversations` | customer | - | The customer's conversations, latest activity first, so a screen finds them again after a refresh |
| `POST /api/conversations` | customer | - | Open a conversation |
| `GET /api/conversations/{id}` | customer who owns it | - | Messages, proposal cards (with the policy citations behind a refusal, and the receipt once refunded), handoffs, who is in control |
| `POST /api/proposals/{id}/confirmation` | customer who owns it | `decision`: confirmed or declined | The confirm button of the proposal card |
| `POST /api/proposals/{id}/cancellation` | customer who owns it | - | Cancel before execution |
| `POST /api/conversations/{id}/handoff` | customer who owns it | - | "Talk to a person": the conversation becomes human_controlled |
| `POST /api/conversations/{id}/messages` | customer who owns it | `text`, 1 to 2000 characters | The chat: the agent answers. 409 while it still answers an earlier message, 503 if the model fails (the message is kept). After a handoff the message is recorded for the person and the model is not asked. |
| `GET /api/staff/queue` | staff | - | Proposals awaiting approval and open handoffs |
| `GET /api/staff/proposals/{id}`, `GET /api/staff/conversations/{id}` | staff | - | One proposal, or one conversation with its history: the audit events of the conversation and its proposals |
| `POST /api/staff/proposals/{id}/decision` | staff | `decision`: approved or rejected; `reason`: required to reject, refused with an approval (422 `valid_values`) | Approve or reject; the policy still applies. After the answer is sent, the agent is told, and pays (if approved) or tells the customer, with the reason |
| `POST /api/staff/handoffs/{id}/take`, `POST /api/staff/conversations/{id}/takeover` | staff | - | Take a handoff, or take over a conversation |
| `GET /api/health` | anyone | - | The database answers |

**What is missing on purpose:** no door proposes or executes a refund. Those are tools of the agent, which runs
inside the backend in the customer's session; the chat door only passes the customer's text on. The agent is built
once when the server starts, and `create_app` refuses one in any configuration but A, so configuration C cannot be
chosen or reached over HTTP; `tests/test_api_surface.py` checks both.

## What the answers promise

- **A body carries only what the door needs.** Any other field, such as an amount, an actor, a customer ID or a
  configuration, makes the request invalid (422), and nothing is changed.
- **Another customer's conversation or proposal is "not found" (404)**, exactly like one that does not exist.
  Refusals by the domain services name the check: 403 for a role, 409 for a conflict with the current state (for
  example `proposal_current` after expiry), 422 for invalid values.
- **A proposal past its validity is shown as expired** (`display_status`) even before the next action closes it;
  `status` is what the database holds.
- **The staff screen keeps text nobody verified apart.** The backend's fields are under `trusted`; the agent's
  summary, the seller's message and the texts of a handoff are under `untrusted`, and the screen must show them as
  plain text (plan section 7). Message text is `content_untrusted` for the same reason.
- **A citation is the policy's own ID** (`refund-policy/v1/return`), with the section's title, never a link a model
  wrote (INV-10).
- **The history shows only what the backend set**: event, outcome, actor, the refused check and a few detail values
  (status, decision, policy reasons, handoff ID and origin). A handoff's reason can be the model's words, so it stays
  under `untrusted` in the queue and is left out of the history.

## Proven by

`tests/acceptance/test_http.py` acts like a browser (cookies included) on a real PostgreSQL and then checks the
database: sign-in and its cookie, the hash in the sessions table, CSRF, sign-out with a kept cookie, expiry, a
restart, the whole flow through the doors, foreign data, roles, extra fields, expiry display, untrusted text, that an
approval through the door still cannot override the policy, the requests and citations the screens show, finding
one's conversations again, and a history that keeps the model's words out. `tests/test_api_surface.py` checks, without a
database, the list of doors and what their bodies accept. `tests/db/test_schema.py` checks that the runtime role
cannot change users or sessions beyond signing out.

## Limits

- No rate limit on sign-in attempts and no account lockout: the demo runs on one machine with fictional users.
- Reading a page is not recorded in the audit log; refused actions are, by the domain services.
- Over plain HTTP the session cookie cannot be Secure; the local demo is the only place that does this.
- One run at a time per conversation is enforced inside one server process. Several server processes would need a
  lock in the database instead; v1 runs one.
- The agent's answer to a staff decision arrives a moment after the decision; the proposal card shows the stored
  state at once, and the screens refresh by polling (plan section 8). The decision stores a notice to the agent in
  the same transaction (`agent_notices`), delivered after the answer is sent, when the server starts and every 5
  seconds, so a server that stops in between loses nothing; the agent applies each notice once. The customer's
  cancellation stores and delivers one the same way, but it starts no answer: the agent reads it with the customer's
  next message.
- In the local demo the agent is the scripted model of mock mode: it plays the chosen scenario's careful agent,
  whatever is typed.
