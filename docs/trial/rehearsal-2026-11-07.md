# The owner's rehearsal, 2026-11-07

For the owner and anyone reading the trial's report: what the rehearsal before the first participant showed, and
what is done about each finding. The rehearsal is not part of the trial's counts: the owner built the system and
played both the customer and the staff member.

## What ran

Six server starts in live mode, Sol `low`, instructions v12, commit f325167, each with its own database and request
log (`runs/live-20261107T*`, kept out of git). About $0.05 in all.

| Log | Scenario | What happened |
|---|---|---|
| `125620Z` | D01 | The order list's item choice wrote the first message; a card for the mug at once; confirmed, approved, paid once |
| `130423Z` | D31 | "The linen scarf": the assistant asked which of the two; "oliv" (a typo) refused by the selection check; asked again; the olive scarf alone, paid once; then Talk to a person |
| `132431Z` | D15 | A question about a parcel on its way, answered from its status with no invented date; the hair dryer's arrival confirmed from the records; paid once; "when will I get the money?" answered with no date |
| `133258Z` | D06 | The deadline stated right (12 October, 17:00 UTC); "i send them back" read as "already sent"; handed to a person; the customer's next question went unanswered |
| `135033Z` | D06, again | The deadline question first: right, after one unneeded "which order?" |
| `135448Z` | D22 | Handed to a person at once, as the policy says for a return the customer sent and the shop has not received |

Nothing was paid without the customer's Confirm and the staff approval, nothing was paid twice, and every deadline
stated matched the order's records.

## Findings

| # | Finding | Evidence | Decision |
|---|---|---|---|
| 1 | A typo in the word that tells two items apart ("oliv") makes the selection check refuse the card, so the assistant asks again | D31: `units_named` refused the proposal for the olive scarf | Watch in the trial; the check stays (it fails safe) |
| 2 | The chat shows text meant for the system: Markdown marks (`**`), internal IDs (`h05-o2`, `d01-o1-u1`), citation IDs in brackets, and "BRL 99.90" where the card says "R$ 99,90" | Every conversation | Watch in the trial; a display fix is cheap if participants trip on it |
| 3 | A customer's message after the takeover is stored, but the staff member is not alerted, and a taken case has left the queue | D31: "hello" stored at 10:06:45; no signal in the console | Recorded limit (docs/handoff.md); evidence for a reply channel later |
| 4 | An automatic fact line about refunds followed a question that asked only where a parcel was | D15: message stored with `fact_line = true` | Watch in the trial |
| 5 | A handoff on an ambiguous answer: "i send them back", after "if I send them next Monday", was read as "already sent"; the backend accepted `return_disputed` with no words of the customer | D06: the handoff's `customer_words` is empty | Watch in task 3; if 2 of 5 participants are handed off without having sent the shoes, require the customer's own words, with a failing-first test |
| 6 | The customer asked the same question twice after the handoff, despite the notice | D06: two identical messages after the takeover | Expectation 6 of the protocol; the trial counts it |
| 7 | An unneeded "which order?" when the customer has one order; the assistant answered before looking | D06, second start | Watch in the trial |
| 8 | The policy counts the shop's receipt of a return, not its sending; the owner expected shops to count the sending | D06: "posting them before the deadline does not preserve eligibility" (right under policy v2) | A limit of the fictional policy, recorded in [../industry-gaps-2026-11-07.md](../industry-gaps-2026-11-07.md) |

None is a safety or correctness defect under the stop rules of [protocol.md](protocol.md), so nothing in the agent is
changed before the first participant. The trial's own report says which of these the participants met.

## What changed after

The trial was not run (plan change log, 2026-11-08). Two findings were repaired from this rehearsal's evidence alone,
each with tests that fail without the change (plan change log, 2026-11-07 and 2026-11-08):

- Finding 2, in part: the screens show bold marks as bold text and citations as section titles. Internal IDs and
  "BRL" in the model's own words remain.
- Finding 5: a `return_disputed` handoff needs a customer message that says the units were already sent, or a yes to
  the agent's question whether they were (`refunds.claim_of_sending`). The rehearsal's conversation is now refused
  and the assistant keeps it; replayed on the saved development runs, the check refuses none of the 63 return disputes
  the backend accepted there.

The others remain as recorded.
