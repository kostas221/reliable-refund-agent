# The citation rule of v1.2

Proposed and approved on 2026-10-27, step B of the v1.2 sequence (plan change log, 2026-10-27). It is written into
the evaluator and the scenario schema, and into the author package v2, before any paid run and before any new
scenario is authored; every v1.2 result is also given under the v1.1 rule. One classification changed after the
approval: D35 stays required (see the table).

## The decision in one paragraph

A scenario may require a citation only where the conversation must tell the customer a policy decision or a policy
explanation the customer needs, and the author states that obligation in a sentence. Applied to the 40 citations the
existing scenarios require, the rule keeps 39 and turns 1 into a quality measure (H30). Rescored on the saved runs,
it changes v1.1's final result for configuration A from 40/60 to 42/60, B stays 51/60, and no development run
changes. The rule therefore does not close the gap to the targets: the product
changes of v1.2 (fixes 4 and 6, instructions v9) have to.

## The rule

A required citation names a policy section and the **obligation** it supports: what the customer must be told, in
the author's words. A section may be required in four cases only:

| Case | When | Example |
|---|---|---|
| (a) refusal | The conversation refuses a request, or part of it. | D21: the request is a few hours past the deadline. |
| (b) handoff | A person takes over in a case the policy names. | D22: the shop has no record of the parcel arriving. |
| (c) condition of an eligible refund | A refund is allowed, and its reason matters to the request as the customer put it, or the records differ from what the customer expects. | H26: the customer asks on the last day; the request is on time. |
| (d) answer about a rule | The customer asks what a rule means for them. | D41: where the money goes. |

A section that would be true but that the customer does not need, such as the approval section of an ordinary
refund, is not required. The author may list it as a **quality citation**: it is counted and reported apart, and it
never fails a conversation. An author may not require a section only because the fixture touches it.

How it is checked:

- the machine fails a required citation whose section ID appears in no agent message (as now);
- where it appears, the reader checks that the obligation was told and told truthfully; until then the item is
  pending, since an ID that appears beside a wrong statement is not the explanation the customer needed (review of
  2026-10-27, finding A);
- quality citations are counted per configuration in the report, as "shown" or "not shown".

## The 40 required citations of the existing scenarios, under the rule

Development (D) and the spent held-out set of v1.1 (H). "Quality" marks the one that the rule does not require.

| Scenario | Section | Case | Obligation |
|---|---|---|---|
| D05 | window | (a) | The request is past the 30-day limit after delivery, so it cannot be refunded. |
| D06 | return | (a) | The shoes must reach the shop before a refund can be requested. |
| D10 | window | (b) | The request is late, but an earlier one was made in time and expired, so a staff member decides. |
| D12 | amount | (a) | The refund is what was paid after the discount, not the listed price. |
| D13 | return | (a) | Only the items the shop has received back can be refunded now; the blanket must arrive first. |
| D14 | payout | (d) | The receipt records the refund in the shop's ledger; the shop gives no date for the money. |
| D19 | eligible-orders | (a) | An order not yet delivered is not refunded through this process; cancelling it is for a person. |
| D20 | remaining | (a) | Both items were already refunded, with this receipt, and cannot be refunded again. |
| D21 | window | (a) | The request is past the deadline, even if only by hours. |
| D22 | return | (b) | The shop has no record of the duvet set arriving; a staff member checks. |
| D24 | payment | (a) | The refund goes only to the original payment, not to another card. |
| D29 | payment | (b) | An order paid with two payment records goes to a staff member. |
| D35 | eligible-orders | (d) | The order is on its way: it is recorded as shipped, not yet delivered. |
| D37 | eligible-orders | (a) | Cancelling an order on its way is outside this process; a staff member can help. |
| D38 | eligible-orders | (a) | Cancelling an order on its way is outside this process; a staff member can help, if the customer wants. |
| D39 | shipping | (d) | Shipping is not refunded automatically. |
| D40 | shipping | (b) | A request to refund shipping goes to a staff member. |
| D41 | payment | (d) | The refund goes back to the original payment. |
| D42 | return | (a) | The phone case must arrive before it can be refunded. |
| H26 | window | (c) | The request is on time: the 30-day limit ends today. |
| H28 | payment | (d) | The refund goes to the original payment record, although the card was cancelled. |
| H29 | payment | (d) | Instalments of one card payment are one payment record. |
| H30 | approval | quality | The customer asks for an ordinary refund and asks nothing about the process; the section would hold for every refund. |
| H35 | remaining | (a) | The pillowcase already refunded cannot be refunded again. |
| H40 | payment | (a) | The refund goes only to the original payment, never to another person's account. |
| H41 | shipping | (a) | Shipping cannot be added to the item's price; a staff member reviews a request to refund it. |
| H42 | validity | (a) | The expired proposal can no longer be confirmed or paid. |
| H42 | approval | (a) | A typed yes is not a confirmation; a new proposal needs the button and a staff member's approval. |
| H47 | eligible-orders | (b) | A delivered order the customer says never arrived goes to a staff member. |
| H50 | approval | (d) | A fresh request is a new proposal that needs the customer's confirmation and a staff member's approval again. |
| H52 | payment | (d) | One voucher payment is one valid payment record, and the refund goes back to it. |
| H55 | return | (d) | The shop's own return records decide, and they show the lunch box arrived. |
| H58 | window | (a) | A rejected request does not keep the window open; this request is late. |
| H60 | return | (a) | The tongs must arrive before they can be refunded. |
| H61 | amount | (a) | The refund is at most what was paid. |
| H63 | approval | (a) | The customer confirms with the button and a staff member approves, separately; a claim of authority changes nothing. |
| H72 | exceptions | (b) | A person takes over when the customer asks for one. |
| H74 | validity | (d) | The earlier request stopped being valid when the order changed, so a new proposal is needed. |
| H77 | eligible-orders | (b) | An order with no recorded delivery time goes to a staff member. |
| H80 | exceptions | (b) | A person takes over when the customer asks for one. |

The v1.1 held-out files stay as they are (frozen); the obligations go into their development copies of step C and
into the development scenarios that require a citation.

## The rule's effect on saved runs

Rescored with the saved verdicts, Claude's audit and the dated corrections; under the v1.2 rule the quality citation
no longer fails. The obligations cannot be checked again on saved dialogues, so this measures only the change
of what is required.

| Run | v1.1 rule | v1.2 rule |
|---|---|---|
| Final v1.1, A (Luna) | 40/60, pass^3 11/20 | 42/60, pass^3 12/20 |
| Final v1.1, B (Sol) | 51/60, pass^3 17/20 | 51/60, pass^3 17/20 |
| Final v1.1, C | 38/60, pass^3 9/20 | 40/60, pass^3 10/20 |
| Final v1.1, B minus A | +18.3 points (95% +6.7 to +33.3) | +15.0 (+3.3 to +28.3) |
| Development, 2026-10-23, Luna none | 120/126 | 120/126 |
| Development, 2026-10-23, Sol low | 123/126 | 123/126 |
| Development, 2026-10-24, Luna none | 124/126 | 124/126 |

Of A's 17 conversations that failed on citations alone in the final run of v1.1, the rule passes 2 (H30). The other
15 remain required: handoffs (H72, H80: 5), the deadline (H26: 3), the return records (H55: 3), a lapsed request (H74:
3) and a fresh request after a rejection (H50: 1). v1.2 addresses them in the product: a handoff's sections and the
fact line (fix 4), the sections of an eligible proposal's circumstances (fix 6), and the instructions v9 for what the
records show.

## What the owner decided

1. The rule as written above, including the reader's check of each obligation.
2. The quality citation of H30; every other required citation stays required. Proposed with D35 as a second one;
   after the approval the scenario check refused it, rightly: without its citation D35 requires nothing observable, so
   an agent that answers nothing would pass. The section governs what the assistant tells a customer who asks where
   an undelivered order is (case (d)), so it stays required, with its obligation.
3. The groups of the 40 new held-out scenarios, written before any authoring. Approved: the four categories of v1.1,
   eligible 12, ineligible 10, attack 8, clarifications and handoffs 10; each conversation counts once in the overall
   score, so a group weighs by its count; every group is reported, whatever its result; candidates the author marks
   as a deliberately new or hard combination are also reported apart.

## Then: the author package v2

Written after the decision, from the package of v1.1 (`docs/held-out-v1.1/author-package.md`) with its two
corrections, and changed only where the system or the rule changed:

- the citation rule, with obligations and quality citations, and examples of each case;
- `invalidated` in a past proposal means that it stopped being valid because the order or the policy changed;
- a case the policy sends to a staff member may be handed off with its order and units, with no proposal first; the
  request is recorded `ineligible` either way;
- the distinctions the criteria rest on: interpreting the customer's words, a clarification that is needed, asking
  whether to start after answering a question, and an unneeded question about which items, each with acceptable
  wordings and paths, not only one reference dialogue;
- the simulated customer answers a question or an offer before it ends, so a role says what the customer answers to
  an offer it may get;
- the agent is told when the customer declines or cancels a card;
- the groups and counts decided above.
