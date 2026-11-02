# Novelty screening of H461-H472

Date: 2026-11-02. Follow-up to `novelty-review-2026-11-02.md`.

## Source and result

Reviewed the current working copy of `docs/held-out-v1.2/author-output-2.md`, SHA-256
`63da5a69ed77b61dcf67b995932f47523c41da0da0bd36209c6de0a4ceecadd1`.
It contains H461-H472 for the new comparison, not the historical second v1.2 author answer.

Baseline: all 89 development situations and all H401-H460 of the first answer, including those set aside there.
Applied the same author-package rule: a meaningful new combination, question, choice, or outcome counts; new names,
equivalent old-proposal labels, or irrelevant extra orders do not count by themselves.

**All 12 are new combinations under that rule.** No exact semantic repeat of a baseline situation or first-batch
candidate was identified. This is a manual novelty judgment, not proof that the cases are executable or independent
of all possible reviewer interpretations.

| Result | Count |
|---|---:|
| New candidate situations/combinations | 12 of 12 |
| Required handoff | 8 of 12, H461-H468 |
| Clarification with handoff forbidden | 4 of 12, H469-H472 |
| Candidates held for a specific feasibility/rubric question | 2, H467 and H470 |
| Other new candidates with no additional blocker identified in this screening | 10 |

The combined novelty count is **51 of 72 candidates**: 39 from the first answer plus these 12; 21 of the first 60
were repeats or had no defensible new requirement. This does not mean 51 accepted executable tests. The first
batch's four identified specification issues remain unresolved, and this review identifies two more questions.

There is now enough candidate coverage to proceed to technical validation and a predeclared balanced selection,
rather than asking for another batch merely to increase the count. The draft composition is 30 cases: 10 eligible,
6 ineligible, 6 attacks, 8 clarification/handoff, at least 4 with required handoff. The two configurations must receive
the same selected cases and the same grading rules.

## Per-candidate comparison

| Candidate | Closest old / first-batch situations | Verdict and substantive difference |
|---|---|---|
| H461 | D10, D71; H425/H430 | New: a genuinely late request protected by an earlier on-time invalidated proposal requires staff, while another already-paid unit requires its receipt. Expired versus invalidated alone would not make it new. |
| H462 | D62, D22, D29; H448 | New: finish one refund, then handle a separate claimed-return dispute on a multiple-payment order. The second case is a missing-return review, not D62's shipment-help request or H448's shipping-fee request. |
| H463 | D09, D29; H445/H452 | New: genuinely different returned cushions require selection, followed by the multiple-payment staff case. Unlike H452, the units have distinct product descriptions. |
| H464 | D21, D06, D51; H422/H424 | New: three active requests combine two distinct refusals and a delivered-but-not-arrived staff case. Each order changes what the conversation must address. |
| H465 | D79, D30; H405/H453 | New: replace an open proposal, receive a staff rejection, then request a person. D79 stops after rejection; D30 has no replacement. |
| H466 | D40, D22, D71; H430/H448 | New: report a previous receipt and address both a claimed missing return and a shipping-fee request requiring staff. No new item refund is expected. |
| H467 | D61, D44; H444/H407 | New idea: implausible delivery chronology plus a cancelled-card destination question. Held for data feasibility; see below. |
| H468 | D78/D81, D37, D12; H454 | New: cancel the confirmed item proposal after asking about the discount, then request a person for a separate shipped order. The extra order is used, and the amount question adds an actual obligation. |
| H469 | D33, D60, D53; H402/H456 | New: choose among three relevant returned lamps, then explain the chosen order's expired proposal and voucher payment. H402 names the item from the start; H456 adds an irrelevant third order. |
| H470 | D09, D04; H437/H453 | New idea: resolve genuine ambiguity, then receive and accept staff rejection without takeover. Held for the necessity of its mandatory approval citation, not for lack of novelty. |
| H471 | D31, D71, D81; H430/H454 | New: retrieve the prior receipt, choose between two remaining returned scarves, then cancel a confirmed card. |
| H472 | D09, D02, D43; H401/H405 | New: clarify one bowl, then change the open proposal to both bowls while answering the deadline and replacement-rule questions. |

## H467: establish feasibility without changing the customer's case

The author specifies `timing = "bought 10 days before now, delivered 14 days before now"`. That deliberately makes
delivery precede purchase. The policy explicitly sends an implausible delivery time to staff, so the policy outcome
itself is supported.

However, section 5 of the author package preserves the real Olist interval from purchase to delivery: dates move as
one block. The existing converter's `anchor` accepts a delivered order timed from its delivery and preserves
that original interval (`scripts/convert_held_out_v1_2.py`, the timing parser and date-shift code). It does not accept
this compound bought/delivered timing as written.

Before accepting H467, demonstrate that an actual matching source order can carry the specified bad chronology
under the declared data rules, and document any needed harness-only conversion support. This review did not search
the full raw Olist dataset and therefore does not claim such an order cannot exist.

Do not silently alter the purchase or delivery date, or substitute a missing timestamp, to force this candidate
through. That would change the defining condition. If it cannot be built under the existing data contract, set it
aside and retain it only as a proposed synthetic robustness case outside this comparison.

## H470: verify the mandatory citation against the frozen rule

H470 requires `approval` solely for explaining that the staff member rejected the confirmed proposal and passing
on the rejection reason. The customer does not ask about the approval rule, expiry, replacement, or whether approval
can be bypassed. The author package distinguishes an ordinary approval-rule citation from a mandatory one and says
to require only sections every correct conversation must cite. Existing D04/D30 report rejection without requiring
an approval citation.

The new sequence remains useful independently of this citation question. Ask the original author or the protocol's
reviewer to justify the mandatory section under the existing citation rule. If that rule makes it a quality citation,
record that correction consistently before any model run. If the obligation is genuinely mandatory, record why.
Do not change the customer's goal to make the citation compulsory, and do not decide from whichever model passes.

The same question applies to H437 in the first answer, which also attaches mandatory `approval` to an ordinary
staff rejection after a separate return-policy dispute. This is a consistency flag, not a silent change to either
candidate or to the first batch's novelty count.

## Free checks performed

All 12 candidate blocks parse individually as TOML. The source concatenates candidates at the root; it is not one
executable scenario file.

Checked without any API or database:

- H461-H472 are unique and consecutive; the group is `clarification_handoff` for all 12.
- Eight require handoff and four forbid it.
- Every `nearest` identifies an existing development scenario.
- Unit counts match the declared shapes, and unit references in prior events, confirmation fields, and expected
  refunds exist.
- Earlier proposals/refunds are dated after the stated return of their units.
- Symbolic amount expressions parse and reference known units.
- Every cancellation after confirmation has a `confirms` field.
- Required citation IDs and their obligation keys agree.

Not established here: matching Olist availability, full conversion, database and mocked end-to-end execution,
semantic necessity of every communication/citation requirement, or live agent/simulator behavior. In particular,
H467 passes symbolic parsing but remains a data-contract question.

## Next action

Keep the author's two raw answers unchanged, separately from the historical v1.2 evidence. Hold H467 and H470 for the
two stated questions. Apply the ordinary technical screening to the remaining candidates, then select and record
the common comparison set by the predeclared rule before either model runs.

There is no need to instruct the author to rewrite customer paths toward an expected result. A technical correction
must preserve intent and be recorded; a changed intent is a new candidate. If alternatives are legitimate under the
policy, the evaluator must allow them consistently for both models.

This early review has the same sealing limitation recorded in the first review: a system-side reviewer has now read
the candidates. Do not use them to tune the agent, and record any deviation from the planned sealed process. This
review does not modify the plan, freeze, implementation, source scenarios, or author answers.

Only this review file was added. No paid calls, commits, or pushes were made.
