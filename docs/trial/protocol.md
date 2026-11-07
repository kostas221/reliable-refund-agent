# The five-person trial: protocol

For the owner, who runs each session as the observer. Section 5 of the release brief
([release-brief-2026-10-31.md](../release-brief-2026-10-31.md)) asks for it; this is how it is run and reported.

Five people use the application with the live model, each for about 45 minutes, while the owner watches and takes
notes. The trial shows where people need help, what they misread and what staff lack. It cannot show a success
rate: five people chosen for convenience say nothing about customers in general, and the report gives counts out of
five, never percentages.

## The questions

The six questions of the release brief, each with what the observer looks at:

| Question | Seen in |
|---|---|
| Where do people need help or repeat information? | Every task: the hints given, and anything the participant had to say twice |
| Do they understand the customer's confirmation and the staff approval? | Task 1: the participant's answer to "What happens now? Has any money been sent?" after Confirm |
| Are refusals and next steps clear? | Task 3: "Can you get your money back? What would you do next?" |
| Are ambiguous selections resolved naturally? | Task 2: whether the assistant asked which scarf, or the participant named it or used the order list |
| Do staff receive enough information to act? | The staff session: "Do you have what you need to decide? What would you check that you cannot see?" |
| Does the workflow reduce staff effort compared with the usual process? | The staff session, only if the participant works or worked in customer support |

## What we expect, written before the first session

Written so that what the trial shows can be told apart from what was assumed. Each is checked in the report.

1. At least one participant types "yes" in the chat instead of pressing Confirm (the card says typing does not
   confirm).
2. At least one participant thinks the money was sent after Confirm, before the staff approval.
3. In task 2 most participants name the scarf's colour in their first message, so the assistant's question is seen
   rarely; the order list's item choice may be used instead.
4. In task 3 every participant can say what to do next (send the shoes back, then ask again before the deadline).
5. In task 4 at least one participant expects the reply in the chat, despite the waiting notice.
6. The staff participant asks for something the console does not show in task 4 (the parcel's tracking).

## Roles and people

- **Customers:** four or five people who use their own English. Each does tasks 1 to 4 ([task-cards.md](task-cards.md)).
- **Staff:** one participant, a person with customer-support experience if one can be found, plays the staff member
  in a session of their own. The owner then plays the customer from the same task cards. If nobody with support
  experience takes part, the report says so and the sixth question stays unanswered.
- **The owner** observes every session. In the customer sessions they also act as the staff member, by a fixed rule:
  approve a card when its items and amount are what the customer asked for in the chat; otherwise reject it with a
  reason that names the difference, and record that as a finding. For task 4 they take the case and write the email
  shown in the task cards' appendix.

Five sessions in all, for example four customers and one staff member. The participants are not told the
expected answers, and the observer gives no help unless a participant asks or is stuck for two minutes; then the
smallest hint, recorded word for word.

## Before the first session

The checks that cost nothing come first.

1. `docker compose up -d`, then each task's scenario in mock mode (D01, D31, D06; D22 has no mock script), both
   screens opened, to see that the scenario loads and the screens show its orders.
2. The owner checks the model's prices on the provider's page and notes the date (`--prices-checked`).
3. A paid rehearsal: the owner does the four tasks once, as a customer, with the commands below (about $0.05).
   Claude reads the four request logs (free) and reports before any participant comes: the conversation, every
   deadline the assistant stated against the order's `refund_deadline`, the citations, and anything a participant
   could misread.
4. Print or open the task cards, the observation form ([observation-form.md](observation-form.md)) and the consent
   note ([consent.md](consent.md)).

## Running a session

Each task runs on its own server start, with a new database and a request log of its own. In Git Bash, the database
once:

```bash
docker compose up -d
```

The screens, in a second terminal, left running:

```bash
cd frontend && npm run dev
```

Each task's server, stopped with Ctrl+C before the next task (D01 shown; then D31, D06, D22):

```bash
uv run --env-file .env python -m refund_agent.api --live --budget-usd 0.25 --prices-checked YYYY-MM-DD --scenario D01
```

The server prints the scenario's customer and staff emails; the password is in `refund_agent/api/__main__.py`. Each
start may spend at most $0.25; a human conversation with Sol `low` is expected to cost a few cents at most. If the
budget or the provider's credit stops the model, the screens say the assistant is paused and nothing is lost; restart
the same scenario with `--keep` and a larger budget.

The order of a customer session:

1. The consent note, read and agreed. The participant's code (P1 to P5) goes on the form, never their name.
2. Open http://localhost:5173 in two browsers: the customer's (signed in by the owner as the task's customer) and
   the staff console (signed in as Rui Costa) in a second browser or a private window.
3. Tasks 1 to 4, each with its card. After each task, the task's question from the form, asked as written.
4. Five minutes of open questions at the end (on the form).

The staff session follows the same tasks with the owner as the customer; the participant works the staff console and
answers the staff questions on the form after each case.

## Stopping a session

Stop at once, keep the database (restart only with `--keep`) and the request log, and tell Claude, if:

- a screen shows money as paid without a receipt, or a receipt the database does not hold;
- a refund is paid without the customer's Confirm and the staff approval, twice, or for items or an amount the
  customer did not ask for;
- the assistant changes anything after the case was handed to a person.

A safety or correctness defect, and a usability problem that stops participants, is fixed with a failing-first test
before the next session; the report says which sessions saw which commit. Other suggestions are recorded for later.

## After each session

- The filled form goes in `runs/live-trial/P<n>.md` (kept out of git, as the request logs are).
- The owner gives Claude the session's log folders (`runs/live-<time>/`). Claude reads them, free, before the next
  session: every deadline stated against the records, what was proposed against what was asked, and anything that
  matches a stop rule.

## The report

`docs/trial/results.md`, written after the last session:

- who took part (codes, how many, whether anyone had support experience), the commits used, and what each session
  cost;
- for each question, counts out of the participants who reached that point ("3 of 5 typed yes in the chat"), with
  short quotes;
- each expectation above: seen or not;
- each problem found: what happened, how often, whether it was fixed (with its test) or recorded for later;
- the limits: five convenience participants, an observer who built the system, fictional accounts and orders,
  simulated money, and tasks chosen to reach each question.
