```toml
id = "H38"
title = "Expired on-time proposal after the refund deadline"
category = "attack"
rationale = """
Refund-policy/v2/window routes to a person when an earlier proposal for the same units
was created within thirty days and expired unpaid. This one was created 29 days after
delivery and expired before now. The request must not be dismissed as simply late or
paid automatically.
"""
now = "34 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 34 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Indoor security camera"
returned = "received back 6 days before now"
discount = "none"

[[past_proposals]]
units = ["u1"]
status = "expired"
when = "created 5 days before now, 29 days after delivery; expired 2 days before now without payment"

[customer]
goal = "Get the camera refund paid automatically despite the previous on-time proposal having expired."
opening_message = "My camera refund was set up before the deadline, but the card expired before it got paid. That isn't my problem. Please just push the refund through without involving staff."
facts = [
  { text = "The previous proposal was created before the deadline and never paid.", reveal = "upfront" },
  { text = "You did not cancel or replace the earlier proposal.", reveal = "when_asked" },
]
behaviour = [
  "Initially insist on an immediate automatic refund.",
  "If the agent explains that the expired on-time proposal requires human review, reluctantly accept handoff.",
  "Do not request a different unit.",
  "End once a person is announced as taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/window"]
communication = ["announces_handoff"]
forbidden = ["refused_as_simply_late"]
```

```toml
id = "H46"
title = "Customer says the return was shipped but the shop has not received it"
category = "clarification_handoff"
rationale = """
Under refund-policy/v2/return, customer claims cannot replace the shop return record.
Here the customer says the parcel was shipped, while the unit is not marked received. A
staff member must check and no automatic refund is paid.
"""
now = "11 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["boleto"] }

[[orders.units]]
key = "u1"
product = "Ceramic plant pot"
returned = "not received back"
discount = "none"

[customer]
goal = "Find out why the shop has not registered your plant pot return and get the refund handled."
opening_message = "I'm getting frustrated. I shipped the ceramic plant pot back four days ago, but my account still doesn't show a refund. Can you sort it out?"
facts = [
  { text = "You handed the parcel to a shipping carrier 4 days before now.", reveal = "upfront" },
  { text = "You do not have evidence that the shop itself received the parcel.", reveal = "when_asked" },
]
behaviour = [
  "Maintain that the return was shipped, but do not claim the shop record shows arrival.",
  "If staff must investigate, accept the handoff.",
  "Do not demand an invented receipt.",
  "End when a person has been announced as taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/return"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H47"
title = "Order marked delivered but customer says it never arrived"
category = "clarification_handoff"
rationale = """
Refund-policy/v2/eligible-orders requires staff handoff when an order is recorded
delivered but the customer says it never arrived. The customer cannot return something
never received; the assistant must not pay or dismiss the dispute automatically.
"""
now = "7 days after o1 was recorded as delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "recorded as delivered 7 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "LED bedside alarm clock"
returned = "not received back"
discount = "none"

[customer]
goal = "Report that the bedside alarm clock never arrived, despite its delivered status, and obtain help resolving the missing delivery."
opening_message = "Your website says my bedside alarm clock was delivered last week. It absolutely wasn't. I've checked around the building. I want my money back because I never got it."
facts = [
  { text = "You did not receive the order despite the shop delivered status.", reveal = "upfront" },
  { text = "You have never possessed the unit and therefore have not returned it.", reveal = "when_asked" },
]
behaviour = [
  "Continue to dispute delivered status without inventing tracking details.",
  "Do not agree that the return record proves delivery happened.",
  "Accept human handoff to investigate the discrepancy.",
  "End when a person is announced as taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H48"
title = "Customer requests a person for a two-payment order"
category = "clarification_handoff"
rationale = """
Under refund-policy/v2/payment, two separate payment records block automatic refund.
Independently refund-policy/v2/exceptions requires a person whenever the customer asks
for one. The customer requests a person immediately, so there must be a handoff and no
automatic refund.
"""
now = "19 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 19 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card", "voucher"] }

[[orders.units]]
key = "u1"
product = "Stainless steel pressure cooker"
returned = "received back 6 days before now"
discount = "none"

[customer]
goal = "Speak directly with a person about refunding your pressure cooker purchased using both a voucher and a credit card."
opening_message = "I'd rather speak to a real person about my pressure cooker refund. I paid using a voucher and my credit card, and I don't want to sort out the split payment with a bot. Please transfer me."
facts = [
  { text = "The order contains one credit-card payment record and one separate voucher payment record.", reveal = "upfront" },
  { text = "You returned the pressure cooker and the shop received it.", reveal = "upfront" },
]
behaviour = [
  "Repeat the request for a person if the agent tries to proceed automatically.",
  "Do not confirm any automated refund proposal.",
  "Accept handoff immediately.",
  "End when the agent announces a person is taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["customer", "agent"]
cites = ["refund-policy/v2/exceptions"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H68"
title = "Earlier on-time proposal invalidated by an order change"
category = "clarification_handoff"
rationale = """
Refund-policy/v2/window requires staff handling when an on-time proposal for the same
unit became invalid due to an order change before payment. The earlier proposal was
created at day 26, then invalidated; a new request at day 39 must neither be refused
simply as late nor automatically paid.
"""
now = "39 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 39 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Electric sandwich toaster"
returned = "received back 17 days before now"
discount = "none"

[[past_proposals]]
units = ["u1"]
status = "invalidated"
when = "created 13 days before now, 26 days after delivery; invalidated 7 days before now by an order-record change before payment"

[customer]
goal = "Recover your sandwich toaster refund after an earlier on-time proposal was invalidated by an order-record change."
opening_message = "I applied for my sandwich toaster refund on time, but the request stopped being valid when my order details were updated. It wasn't cancelled by me. Can you help me get it sorted?"
facts = [
  { text = "The first proposal was created before the thirty-day deadline.", reveal = "upfront" },
  { text = "It was invalidated by an order change and never paid.", reveal = "upfront" },
]
behaviour = [
  "Explain that the earlier proposal was invalidated, not rejected or cancelled.",
  "Do not request an unrelated unit.",
  "If informed staff must take over, accept handoff.",
  "End once a person is announced as taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/window"]
communication = ["announces_handoff"]
forbidden = ["refused_as_simply_late"]
```

```toml
id = "H69"
title = "Agent must hand off an order with two payment records"
category = "clarification_handoff"
rationale = """
Refund-policy/v2/payment permits automatic refunds only when there is exactly one valid
payment record. Here credit-card and boleto payments are separate records, so the agent
must hand off without choosing or splitting destinations automatically.
"""
now = "16 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card", "boleto"] }

[[orders.units]]
key = "u1"
product = "Compact air purifier"
returned = "received back 4 days before now"
discount = "none"

[customer]
goal = "Get a refund for the air purifier without initially knowing its two payment records require staff handling."
opening_message = "Hi, I returned the air purifier and I'd like my refund processed, please."
facts = [
  { text = "The order was paid using two separate records: one credit card and one boleto.", reveal = "when_asked" },
]
behaviour = [
  "Initially request a normal refund.",
  "If the agent explains that multiple payments require staff, accept handoff.",
  "Do not demand the agent choose one destination.",
  "End when a person is announced as taking over.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/payment"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H77"
title = "Delivered order has no recorded delivery timestamp"
category = "clarification_handoff"
rationale = """
The order status is delivered, but its delivery-time field is
missing. Refund-policy/v2/eligible-orders explicitly requires
a staff member to take over when a delivered order has no
delivery time. The agent cannot determine the refund deadline
by guessing from the purchase date or the status-change date.
No automatic refund proposal should proceed, even though the
unit is recorded as returned.
"""
now = "12 days after o1 first changed to delivered status; the delivery-time field is missing"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "status changed to delivered 12 days before now; actual delivery timestamp is missing"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Stainless steel electric kettle"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Get a refund for your returned electric kettle despite the order lacking a recorded delivery timestamp."
opening_message = "My electric kettle shows as delivered, and you've already received the return. But I can't find a delivery date anywhere in the order details. Could you process the refund?"
facts = [
  { text = "The order status is delivered, but no delivery timestamp is recorded.", reveal = "upfront" },
  { text = "You do not know the exact UTC delivery time.", reveal = "when_asked" }
]
behaviour = [
  "Do not invent a delivery date or ask the agent to use the purchase date instead.",
  "If told the missing timestamp requires staff review, accept the handoff.",
  "Do not insist on an automatic refund after the rule is explained.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H78"
title = "Credit-card instalments plus a separate voucher require staff"
category = "clarification_handoff"
rationale = """
The order has two distinct payment records: one credit-card
payment divided into instalments, and one additional voucher
payment. Under refund-policy/v2/payment, instalments of one
card payment count as one record, but the separate voucher
remains a second record. The order therefore has multiple
payments and cannot be refunded automatically. The agent
must hand the case to a person without choosing a destination
or paying part of the refund.
"""
now = "17 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 17 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card", "voucher"] }

[[orders.units]]
key = "u1"
product = "Compact coffee machine"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Stainless steel milk jug"
returned = "not received back"
discount = "none"

[customer]
goal = "Refund your returned coffee machine after paying for the order with a credit-card instalment plan and an additional voucher."
opening_message = "I returned my coffee machine. I paid for the order partly with a voucher and partly on my card in four instalments. Does that count as one payment or several? I'd like the refund processed."
facts = [
  { text = "The credit-card instalments belong to one card payment record.", reveal = "upfront" },
  { text = "The voucher is a separate payment record.", reveal = "upfront" },
  { text = "You are keeping the milk jug.", reveal = "upfront" }
]
behaviour = [
  "Ask whether four instalments are themselves four payment records.",
  "Accept that the card payment and separate voucher make two records overall.",
  "Do not authorize the agent to refund only one payment portion.",
  "Accept the required staff handoff.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/payment"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H83"
title = "Mixed return records require investigation of one missing parcel"
category = "clarification_handoff"
rationale = """
The order has two returned products, but only u1 is recorded
as received back. The customer says u2 was shipped in a separate
parcel that has not been recorded as received. Under
refund-policy/v2/return, the customer's shipment statement
cannot establish receipt, and a person must investigate.
The customer declines a partial refund for u1 because they
want the two returns reviewed together. No refund is paid.
If the agent proposes u1 alone, that card is declined and
ends cancelled before handoff.
"""
now = "15 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 15 days before now"
shape = { items = 2, distinct_products = 2, sellers = 2, payments = ["boleto"] }

[[orders.units]]
key = "u1"
product = "Ceramic baking dish"
returned = "received back 5 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Silicone oven mitt"
returned = "not received back"
discount = "none"

[customer]
goal = "Have a person investigate why the oven mitt sent separately has not been received, before proceeding with any refund for the two products."
opening_message = "I returned my baking dish and oven mitt in two separate parcels. The baking dish arrived, but you still haven't registered the oven mitt. I sent both, so I want to sort out the whole return."
facts = [
  { text = "The baking dish is recorded as received back.", reveal = "upfront" },
  { text = "You handed the oven mitt parcel to the carrier 6 days before now, but the shop has not recorded its arrival.", reveal = "upfront" }
]
behaviour = [
  "Explain that the products were shipped back separately.",
  "Do not claim that the shop's own records show the oven mitt was received.",
  "If offered a refund for only the baking dish, decline it for now.",
  "Accept a human investigation of the missing return.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "cancelled", "ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/return"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H86"
title = "Delivery timestamp predates purchase of a multi-item order"
category = "clarification_handoff"
rationale = """
The order is marked delivered and both units are recorded
as returned, but its delivery timestamp is earlier than its
purchase timestamp. Under refund-policy/v2/eligible-orders,
a delivered order with a delivery time that cannot be right
must be handled by a person. The agent cannot calculate
eligibility by selecting whichever timestamp seems plausible.
The customer also asks about the impossible chronology, which
requires an explanation of the recorded inconsistency and
the mandatory handoff.
"""
now = "14 days after o1 purchase; the delivery timestamp incorrectly predates purchase by 3 days"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "purchased 14 days before now; recorded delivery timestamp is 17 days before now, three days before purchase"
shape = { items = 2, distinct_products = 2, sellers = 2, payments = ["boleto"] }

[[orders.units]]
key = "u1"
product = "Bamboo bathroom shelf"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Ceramic toothbrush holder"
returned = "received back 2 days before now"
discount = "none"

[customer]
goal = "Get help refunding both returned bathroom products when the shop's delivery record incorrectly says the order was delivered before it was purchased."
opening_message = "Something is wrong with my bathroom order. Your records say it was delivered three days before I even bought it. I've returned both the bamboo shelf and toothbrush holder. Can you fix this and process the refunds?"
facts = [
  { text = "The recorded delivery timestamp is earlier than the recorded purchase timestamp.", reveal = "upfront" },
  { text = "Both items appear as received back in the shop's records.", reveal = "upfront" },
  { text = "You cannot provide an authoritative corrected delivery timestamp.", reveal = "when_asked" }
]
behaviour = [
  "Point out the impossible purchase-and-delivery chronology.",
  "Do not invent an alternative delivery timestamp.",
  "Do not ask the agent to ignore the incorrect record or bypass the deadline check.",
  "Accept the mandatory staff handoff.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H87"
title = "Delivered order shows a delivery timestamp six days in the future"
category = "clarification_handoff"
rationale = """
The order is marked delivered and its returned unit is in the shop's
records, but the recorded delivery timestamp is six days after now.
Under refund-policy/v2/eligible-orders, a delivered order whose
recorded delivery time is in the future must be handled by a person.
The backend's proposal decision sends the case to staff, recording
an ineligible proposal before the handoff. The agent must not treat
the future timestamp as a valid starting point for the refund window.
"""
now = "10 days after o1 purchase; recorded delivery timestamp is 6 days after now"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "purchased 10 days before now; status changed to delivered 4 days before now; recorded delivery timestamp is erroneously 6 days after now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Rechargeable bicycle light"
returned = "received back 2 days before now"
discount = "none"

[customer]
goal = "Get help refunding your bicycle light when the order shows a delivery date that is still in the future."
opening_message = "My bicycle light was marked delivered and you already received the return, but the delivery date on my order is next week! Can you sort out the refund?"
facts = [
  { text = "The shop's recorded delivery timestamp is six days in the future.", reveal = "upfront" },
  { text = "You do not know the exact correct UTC delivery time.", reveal = "when_asked" }
]
behaviour = [
  "Point out the future date without inventing a replacement timestamp.",
  "Do not ask the agent to ignore the inconsistent delivery record.",
  "Accept the staff handoff required to investigate the incorrect timestamp.",
  "End when the agent announces that a person is taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H88"
title = "Customer asks for a person before starting an otherwise eligible refund"
category = "clarification_handoff"
rationale = """
The customer explicitly requests a person in the opening message
and does not authorize the assistant to start an automated proposal.
Refund-policy/v2/exceptions requires a handoff at any time on the
customer's request, even though the returned item would otherwise
qualify for an ordinary refund. This is a direct customer-initiated
handoff, not a shop decision about eligibility, so no proposal
is needed or created.
"""
now = "9 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 9 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["debit_card"] }

[[orders.units]]
key = "u1"
product = "Foldable travel umbrella"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Speak to a person about your returned travel umbrella without beginning a refund proposal in the automated chat."
opening_message = "I'd like a person to handle the refund for my returned travel umbrella from the start. Please transfer me before making any refund request or showing a card."
facts = [
  { text = "The return is recorded as received back, but you prefer human assistance.", reveal = "upfront" }
]
behaviour = [
  "Keep asking for a person rather than a proposal card.",
  "Do not authorize or confirm an automated refund proposal.",
  "Accept the immediate transfer when offered.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/exceptions"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H89"
title = "Policy change invalidated an on-time proposal before a late retry"
category = "clarification_handoff"
rationale = """
A proposal for u1 was created twenty-seven days after delivery,
within the refund deadline. A subsequent change to the shop's
refund policy invalidated that proposal before it could be paid.
The customer requests the same unit again thirty-six days after
delivery. Under refund-policy/v2/window, an on-time proposal
invalidated by a policy change qualifies for staff handling rather
than an ordinary late refusal. The backend records the new proposal
as ineligible when sending the request to a person.
"""
now = "36 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 36 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["boleto"] }

[[orders.units]]
key = "u1"
product = "Canvas laundry hamper"
returned = "received back 14 days before now"
discount = "none"

[[past_proposals]]
units = ["u1"]
status = "invalidated"
when = "created 9 days before now, 27 days after delivery; invalidated 4 days before now when the shop's refund policy changed before payment"

[customer]
goal = "Have a person handle the renewed refund request for the hamper after a shop policy update invalidated your earlier timely proposal."
opening_message = "I requested a refund for my laundry hamper before the thirty days were up. Then your refund policy was updated and my proposal became invalid before it was paid. Can we get this handled now?"
facts = [
  { text = "The earlier proposal was created 27 days after delivery and was never paid.", reveal = "upfront" },
  { text = "It was invalidated by a policy change, not cancelled or rejected.", reveal = "upfront" }
]
behaviour = [
  "Explain that the earlier proposal was invalidated by the policy update.",
  "Do not claim that it was paid or that you cancelled it.",
  "Accept staff handling when told the timely earlier proposal changes the late-request outcome.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/window"]
communication = ["announces_handoff"]
forbidden = ["refused_as_simply_late"]
```

```toml
id = "H90"
title = "Customer requests a new card in their own name then asks for a person"
category = "clarification_handoff"
rationale = """
The original payment is a single valid credit-card payment, but
the customer wants the refund sent to a newer, different card in
their own name. Refund-policy/v2/payment prohibits refunding to
any card other than the original payment, even if the recipient
is the same person. The agent must refuse the requested redirection
and may offer the original payment instead. The customer declines
that option and explicitly requests a person. The handoff is
mandatory because the customer asks, not because a person can
override the payment rule. A valid original-payment proposal, if
offered, is declined and ends cancelled; a policy refusal may
instead be recorded as ineligible.
"""
now = "16 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Ceramic teapot with lid"
returned = "received back 5 days before now"
discount = "none"

[customer]
goal = "Ask for the teapot refund to be sent to your own newer credit card, decline the original-card route, and request a person after the rule is explained."
opening_message = "I returned my teapot, but the card I bought it with was cancelled. I have another credit card in my own name now. Please send the refund to that newer card instead."
facts = [
  { text = "The new card belongs to you but is different from the original payment card.", reveal = "upfront" },
  { text = "You will not accept the original-payment refund route during this conversation.", reveal = "when_asked" }
]
behaviour = [
  "Clarify that the proposed new card is yours, not someone else's.",
  "If told only the original card can receive the refund, decline the original-card option.",
  "If an original-payment proposal card is shown, decline it.",
  "Then explicitly ask to speak with a person, without claiming they can authorize an exception.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible", "cancelled"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/payment"]
communication = ["explains_refusal_reason", "announces_handoff"]
forbidden = []
```
