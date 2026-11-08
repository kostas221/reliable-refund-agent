# The demonstration video

For the owner, who records the 2 to 3 minute video, and for a viewer who wants to repeat it. Everything runs in mock
mode, so the recording can be repeated exactly and costs nothing. Say so on screen: a fixed script plays the agent,
and the payments are entries in a test ledger. If a live-model clip is added, the owner starts that paid session and
labels it as live.

## Before recording

1. Docker running; nothing else on ports 8000 and 5433.
2. Start the demo application, scenario D01 (Ana Lima's chipped mug):

   ```bash
   docker compose --profile app up --build
   ```

3. Two browser windows side by side on http://localhost:8000: a normal one signed in as `ana.lima@example.test`,
   a private one signed in as `rui.costa@shop.example.test` (password `refund-demo-local` for both).
4. A terminal in the repository, for step 5.

## The storyboard

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:00 | Both windows: the banner, Ana's orders, Rui's empty queue | "A customer and a staff member of a fictional shop. This is mock mode: a fixed script plays the agent, and no money moves, payments go to a test ledger." |
| 2 | 0:15 | Ana types "Hi, I sent back the blue mug because it arrived chipped. Can I get a refund?"; the card appears | "The model asks the backend for a proposal. The backend checks the order is hers, that the mug came back in time, and computes the amount. The model never sends an amount." |
| 3 | 0:40 | Ana presses Confirm refund of R$ 49,90; the card says Waiting for staff approval | "Only the button confirms. Typing yes in the chat does not." |
| 4 | 0:55 | Stop the server (Ctrl+C in its terminal); both windows say "No answer from the server. Nothing is assumed" | "A crash while the approval is pending." |
| 5 | 1:05 | Start it again on the same database: `docker compose --profile app run --rm --service-ports app --keep`; reload both windows | "The confirmation was committed, so it survives. Nobody signs in again." |
| 6 | 1:25 | Rui opens the request: the backend's figures in the green box, the assistant's summary in the dashed "Not verified" box; Approve refund of R$ 49,90 | "The staff member approves this exact proposal. Nothing the model wrote can change what is paid." |
| 7 | 1:45 | Ana's card: Refunded, receipt R-00000001 | "One transaction checks everything again, writes the ledger and returns the receipt." |
| 8 | 2:00 | In Ana's window, open http://localhost:8000/api/staff/queue: `{"detail":"this door is for staff"}` | "A customer cannot reach a staff door; the backend refuses it, whatever the screen shows." |
| 9 | 2:10 | Terminal: `REQUIRE_DB=1 uv run pytest tests/acceptance/test_first_refund.py -v -k every_retry`, then the test's lines on screen | "Paying before the approval is refused, and a retry after a lost answer returns the same receipt: one refund, never two." |
| 10 | 2:30 | The README's evidence table | "Measured on unseen scenarios at every version. The latest: 109 of 117 conversations with GPT-6.1 Sol, and no unauthorized or duplicate refund in any run. Fictional shop, simulated money, local only." |

Step 9 needs the development setup (uv and the database on port 5433, which the Docker stack also provides). If it
is left out, say the same over the README's line on failure cases.

## Checks after recording

- The video shows the mock-mode banner at least once and says that payments are simulated.
- No claim of production readiness, of zero risk, or of a success rate beyond the held-out results with their
  versions.
- Nothing personal is visible: the screen shows only the fictional users, and no terminal shows `.env`.
