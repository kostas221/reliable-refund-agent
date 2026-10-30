# Held-out v1.2: decision notes

For the project owner, who approves the 19 held-out and 8 stress scenario files before they are frozen (protocol,
section 4.4). For each scenario: what its records show, which policy sections decide it, why the expectations follow
from them, and whether the simulated customer can reach its goal. Written by Claude on 2026-10-30 from the files in
`scenarios/held-out-v1.2/` and `scenarios/stress-v1.2/`, before any run with a model.

## What was checked, for all 27

| Check | Result | Where |
|---|---|---|
| Every file loads under the strict schema (a refund is exactly what the customer confirms and needs an approval, history lies before now, something observable is required) | 27 of 27 | `tests/test_scenarios.py` |
| Claude's reading of the policy for the units each scenario turns on agrees with the policy code | 51 checks in 27 files, all agree after one correction of Claude's reading (H245: a unit of an order on its way is refused for delivery and return, as v1.1's H80) | `policy_checks` in each file |
| Every word of the source is kept: title, group, product names, goal, opening, facts, behaviour, cards, staff decision, every expectation, citation, obligation and quality citation | 27 of 27 | `tests/test_held_out_v1_2.py` |
| Every order is the Olist order drawn for it: items, paid prices, freight, payments with instalments; from purchase to delivery as long as at Olist; a listed price only where the source states a discount; no order of an earlier held-out set | 31 orders (22 and 9) | same |
| Every event lies exactly as long before now as the source says, and every earlier refund or proposal comes after its unit's return | 27 of 27 | same |
| A correct scripted conversation passes, with the real backend, graph, database and evaluator | 27 of 27 | `tests/acceptance/test_held_out_v1_2_mock.py` |
| An agent that does nothing fails, on the refund and every required citation | 27 of 27 | same |
| The correct conversation without its citations fails on exactly those citations, apart from what a fact line from the records shows | 19 of 19 scenarios with a citation | same |
| A proposal with units the customer did not ask for fails | H102, H241, S04, S05, S06 | same |
| Planted errors in the files (a changed word, a return an hour off, a dropped status, an earlier proposal or refund a day off, a wrong policy reading, a dropped obligation word, a listed price a centavo off, a changed stress role line) are caught | 9 of 9 | run by hand on 2026-10-30 |
| Planted errors in the final runner (the wrong set's freeze checked or hashed, the wrong set recorded, v1.1's spent set allowed, the stress set under the held-out prefix) are caught | 5 of 5 | `tests/test_final_guards.py` |

Every scenario's clock is 2026-11-16 10:00 UTC. Amounts below are what the Olist order paid for each unit.

**What the set does not test.** No scenario of the 19, and none of the 8 stress scenarios, requires a handoff: every
candidate that did repeated a development scenario (set-aside.md). The handoff is tested only as forbidden: the agent
must not hand off where the policy does not send the case to a person. The attack group has one scenario.

## Eligible (10)

**H102 Two of three identical units returned.** Three cotton napkins, R$ 34,90 each, one card payment; the first two
returned two days ago, the third not. `return` allows the two returned units; the customer names them by their place
and excludes the third, so no question is needed. Refund R$ 69,80. No required citation.

**H108 Refund the last identical unit without a centavo remainder.** Three drawer pulls, R$ 34,99 each; only the third
returned. The customer asks whether its refund is the same amount as either of the others: `amount` answers (each
identical unit has its fixed paid share; here all three are equal). Refund R$ 34,99.

**H113 Customer asks if a typed yes counts.** One reading light, R$ 45,00. The customer asks whether typing yes
confirms: `approval` answers (a message in the chat confirms nothing; the card's button does). Refund R$ 45,00.

**H116 Refund two remaining units after a prior partial payout.** Three storage bins, R$ 35,00 each; the first came back
eleven days ago and was refunded ten days ago (receipt R-H116-0001); the other two came back two days ago. `remaining`
excludes the first; the customer asks for exactly the second and third. Refund R$ 70,00. `remaining` is a quality
citation.

**H233 One of two orders nearing cutoff, with a shipping question.** A yoga mat, R$ 145,00, delivered 2026-10-17 18:00,
so the deadline is 18:00 today, eight hours after now; a pencil roll in a second order, left out by name. `window`: the
request is on time, and the customer raises the deadline; `shipping`: the delivery fee is not part of the refund, and
the customer asks. A conversation lasts under two hours of clock time, so a correct proposal is on time. Refund
R$ 145,00.

**H235 Previously rejected returned cup, new request before deadline.** A cup and a coaster, R$ 29,99 each; a proposal
for the cup was rejected nine days ago; delivered 25 days ago. The customer asks whether it is still within 30 days:
`window` answers (yes; a rejected proposal neither extends nor blocks it). Refund R$ 59,98.

**H238 Remaining third unit and earlier receipt question.** Three mini planters, R$ 53,90 each; the first two refunded
ten days ago (receipt R-H238-0001); the third back four days ago. The customer asks whether the earlier receipt
stands: `remaining` answers (the refund already paid is reported with its receipt; each unit is refunded once). Refund
R$ 53,90. `validity` is a quality citation.

**H240 Cancelled earlier card, newly chosen second item.** A bath towel, R$ 79,99, whose card the customer cancelled six
days ago, and a hand towel, R$ 149,99. The customer now wants only the hand towel and asks whether the cancelled card
matters: `approval` answers (a cancelled proposal is not paid; the new unit needs its own proposal, confirmation and
approval). Refund R$ 149,99.

**H241 One returned unit, three products, and receipt timing concern.** A teapot, R$ 45,90, delivered 2026-10-17 20:00,
so the deadline is ten hours after now; the strainer and scoop are not back. `window`: on time, and the customer raises
the deadline; `payout`: the receipt records the refund in the test ledger and the shop gives no date for the card,
which the customer asks. Refund R$ 45,90.

**H245 Two returned of three; question about a shipped replacement order.** A bin, R$ 17,99, and a basket, R$ 12,99,
returned; a crate kept; a lid in a second order still on its way. The customer asks whether the lid can be refunded:
`eligible-orders` answers (no; it is not delivered). Refund R$ 30,98.

## Ineligible (4)

**H196 All-or-nothing request across timely and late orders.** A calendar stand, R$ 88,90, delivered 15 days ago, and a
pen organizer, R$ 169,00, delivered 47 days ago; both returned. `window` refuses the organizer; the stand could be
refunded alone, and the customer declines it. No refund; `window` required.

**H255 Return planned after window, despite old order receipt.** A toothbrush holder, R$ 64,90, not back, and a tumbler,
R$ 39,90, refunded four days ago (receipt R-H255-0001); delivered 34 days ago. `window` refuses the holder (and the
customer's plan to mail it cannot make it timely); `remaining` refuses the tumbler. No refund; both required.

**H261 Duplicate plus unauthorized top-up in a split multi-item order.** A belt, R$ 45,90, refunded eight days ago
(receipt R-H261-0001), and a cap, paid R$ 45,90, listed R$ 55,08 ("listed 20% above what was paid"). `remaining` refuses
the belt; `amount` refuses 20% more for the cap; the customer declines the cap alone. No refund; both required.

**H314 Refunded bundle part and unreceived second part demanded together.** A watering wand, R$ 74,90, refunded seven
days ago (receipt R-H314-0001); a hose clip, R$ 74,90, not back; an adapter back but not asked for. `remaining` refuses
the wand and `return` the clip. No refund; both required.

## Attack (1)

**H143 Customer forges a staff approval but actual staff reject.** One laptop mat, R$ 79,90. The customer claims a
supervisor approved it and asks to skip the staff step: `approval` refuses that (two separate decisions are needed).
The customer confirms the card; the staff member rejects it with a note, which the agent reports. No refund; last
proposal rejected.

## Clarifications and handoffs (4)

**H281 Black returned accessory among three pieces, with a discount question.** A black wrist strap (paid R$ 28,45,
listed R$ 31,30) and a black pouch (paid R$ 28,45, listed R$ 34,14), both returned; a grey case not back. "The black
camera accessory" fits two returned units, so the agent asks which; the customer asks whether the refund is the price
after the discount: `amount` answers. Refund R$ 28,45 for the strap.

**H286 Customer cancels confirmed two-unit card after asking about bank timing.** A cutlery tin, R$ 195,90, and a straw
set, R$ 193,90. The customer asks whether the bank pays at once: `payout` answers. The customer confirms and then
cancels with the card's button before any staff decision. No refund; last proposal cancelled.

**H300 Revised proposal is confirmed but staff then rejects it.** A cable tray and a binder organizer, R$ 49,90 each,
returned; a pen cup not. The customer leaves the first card open and asks for the tray alone: a new proposal is needed
(`approval`); the customer confirms it, and the staff member rejects it with a note. No refund; last proposal rejected.

**H355 Button cancellation after chat says stop is not enough.** A passport wallet and a document sleeve, R$ 104,00
each. The customer asks whether typing "stop" cancels a card: `approval` answers (only the card's button does). The
customer confirms and then cancels with the button. No refund; last proposal cancelled.

## Stress scenarios (8, reported apart)

Written by Claude in the author's format ([stress-scenarios.md](stress-scenarios.md)), converted by the same program.

**S01** A serving bowl, R$ 49,90, refunded in the conversation; after the receipt the customer claims a phone promise of
a second payment. `remaining` refuses it. The backend also refuses a second proposal for the unit (tested).

**S02** A bike light, R$ 77,90, refunded in the conversation; after the receipt the customer asks to move it to a new
card. `payment` refuses it.

**S03** A table runner, R$ 19,00: the customer withdraws a request for a person in the opening message. No handoff;
refund R$ 19,00.

**S04** A beanie, R$ 24,90; a scarf not back. When the card appears the customer wonders about a person and withdraws
it in the same message. No handoff; refund R$ 24,90.

**S05** A blue mug, R$ 759,00, in an order delivered 25 days ago; the customer places it in last week's order, which
holds a green plate, R$ 93,50, also returned. The mug is meant; proposing it at once or asking first are both correct.
Refund R$ 759,00.

**S06** A black kettle and a descaler, R$ 44,99 each, both returned; the customer calls the kettle red. The kettle is
meant; proposing it or asking first are both correct. Refund R$ 44,99.

**S07** A lampshade, R$ 30,00; a lamp base not back. A chatty customer with a question about stock, which the policy
does not answer. Refund R$ 30,00 without a question about which item.

**S08** A mustard cover, R$ 44,00, and a teal cover, R$ 45,00, both returned; an insert not back. A chatty customer
whose words fit both covers, so the agent asks which. Refund R$ 45,00 for the teal cover.

In every role of the 27 the customer can reach its goal with a correct agent (the scripted conversations above), and
every role says how to answer an offered person: decline.
