# Comparison set of v1.3: decisions for the owner before the freeze

**Approved on 2026-11-03.** The owner approved the 39 files and the decisions below as recommended ("Yes, freeze
them"), and the set was frozen (`scenarios/held-out-v1.3/FROZEN`).

For the project owner, who approves the 39 scenario files before they are frozen (protocol, section 4). Written on
2026-11-03 by Claude after the conversion. Each point is a choice the author's text did not settle. Each gives what
was done, why, and the alternative. Nothing here changes the agent; the agent is the one of the comparison
(commit `80c5a0b` with the Anthropic adapter).

Files: `scenarios/held-out-v1.3/` (39), written by `scripts/convert_held_out_v1_3.py` from the selected blocks. Each
block is checked against the SHA-256 in `selected-39-manifest.json`. The orders were drawn by
`uv run python -m refund_agent.olist v1.3` (`data/olist/subset-v1.3.json`, 63 orders, none from an earlier set). Every
value the author did not state is listed in [conversion-log.md](conversion-log.md).

## Decisions to approve

1. **H421's payment, a synthetic split.** The author wrote an order paid by credit card and boleto. No Olist order has
   that pair: the draw found none in 99,441 orders. The order is a real one-item order paid by card. Its one payment
   of 64.10 is split into a card record of 32.05, which keeps the 5 instalments, and a boleto record of 32.05. The
   total is unchanged, and this is the set's only synthetic payment record. What the scenario tests holds: a refusal
   for an unreturned item does not become a staff case because the order has two payment records. *Alternatives:*
   relabel the voucher record of a real card-and-voucher order as boleto, or set H421 aside and run 38. Recommended:
   the split.
2. **H422's product name, kept as the author wrote it.** The third order's product is "Siliconeoven mitts", a typing
   slip; the role says "silicone oven mitts". The order has one item, so no check depends on matching the words.
   Recommended: keep the author's text, as every other word is kept. *Alternative:* correct it to "Silicone oven
   mitts" and record the change.
3. **File names cut at 60 characters.** The template, which names the file, is the author's title in lower case with
   hyphens, cut after the last whole word within 60 characters. The full titles gave names of up to 194 characters,
   and full paths of 255 on this computer, within 5 of Windows' 260-character limit. A worktree or CI checkout in a
   deeper folder would break. The titles inside the files are unchanged.
4. **The clock and the people.** Every scenario's now is 2026-11-16 10:00 UTC, as in v1.1 and v1.2. Each customer has
   a synthetic name. The three other customers are synthetic too: H407's is unrelated, H432's is a coworker, and
   H438's sister shares the customer's surname, as the role suggests. The agent must disclose nothing about any of
   them.
5. **Unit labels in the roles: a limit, not changed.** 19 of the 39 roles name units by the author's labels, for
   example "specify the brass floor lamp (u2)". In v1.2, 3 of 19 did. The simulated customer reads them and may
   write "u2", which matches the end of the unit's ID in the agent's tools (`h469-o2-u2`). Both models meet the same
   simulated customer and the same text, so the comparison stays fair, but such a message makes a question easier
   to answer. Recommended: keep the author's text and count, in the run, the customer messages that name a label.
6. **H407's title** speaks of a seller message, and the scenario has none. It is the author's title, and no check
   reads it.

## What the free checks showed

- **Fidelity** (`tests/test_held_out_v1_3.py`, 205 tests). Every word of the author is kept. Every order is the one
  drawn, with the author's shape (status, items, products, sellers, payment methods) and ties: the same product with
  another customer in H407, H432 and H438, and the same category with another product in H469. Every time is exact
  to the hour, including H472's deadline 12 hours away. Another customer's order is hidden from the agent, and each
  block's hash is the manifest's.
- **The shared rules** (`tests/test_scenarios.py`): the policy checks of all 39 agree with the policy code, the
  arithmetic adds up, and the simulated customer gets only what the customer knows.
- **Mocked conversations** (`tests/acceptance/test_held_out_v1_3_mock.py`). A scripted correct conversation passes in
  all 39, through the real backend, database and evaluator, with no backend refusal. An agent that does nothing
  fails all 39. The correct conversation without its citations fails exactly on them. A proposal with units the
  customer did not want fails in H403, H406 and H416; in H469 the selection check refuses it before any card exists.
  A late refusal where the policy sends H461 to a person fails. A handoff the customer did not ask for is refused by
  the backend (H420), and one the scenario forbids fails (H420).
- **Planted errors.** Each was put in one file, and all 12 were caught: a word of a goal, a paid amount, a delivery
  an hour off, another customer's order shown to the agent, a seller message, a dropped citation, a past proposal's
  status, a policy check, the split payment's total, a return a day off, a staff note, and the card behaviour.

## What remains before the run

After the owner approves these files, the set is frozen (`scenarios/held-out-v1.3/FROZEN`). Then, in this order, all
before the run:

- the targets, the predictions and the decision rule;
- the choice of simulated customer (protocol, section 5);
- the final runner's two configurations, Sol `low` and Sonnet `low`, with a budget cap.
