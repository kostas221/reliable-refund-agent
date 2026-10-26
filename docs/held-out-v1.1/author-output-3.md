```toml
id = "H73"
title = "Refund remaining units after one of three was already paid"
category = "eligible"
rationale = """
The order contains three returned physical units. An earlier
refund already paid for u1, while u2 and u3 remain unrefunded.
Under refund-policy/v2/remaining, each unit can be refunded
only once. The customer explicitly accepts a refund for the
two outstanding units, so the agent must propose only u2 and
u3, for paid(u2) + paid(u3). The previous refund and receipt
remain historical and must not be included in the new payout.
"""
now = "16 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 3, distinct_products = 3, sellers = 2, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Cotton kitchen apron"
returned = "received back 11 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Silicone baking mould"
returned = "received back 5 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Stainless steel cooling rack"
returned = "received back 3 days before now"
discount = "none"

[[past_refunds]]
units = ["u1"]
when = "8 days before now"

[customer]
goal = "Find which products from your three-item return are still awaiting refunds and receive the outstanding amounts without refunding anything twice."
opening_message = "I returned my apron, baking mould and cooling rack separately. I think the apron was refunded already. Could you check which ones still need a refund and process just those?"
facts = [
  { text = "You remember receiving an earlier refund for the apron.", reveal = "upfront" },
  { text = "You want only units that have not yet been refunded.", reveal = "upfront" }
]
behaviour = [
  "If asked, confirm that you do not want the apron refunded again.",
  "Accept the agent's identification of the two remaining refundable units.",
  "Confirm only a proposal for the baking mould and cooling rack.",
  "Decline a person.",
  "End after the new refund receipt is provided."
]
confirms = { units = ["u2", "u3"], amount = "paid(u2) + paid(u3)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u2", "u3"]
refund_amount = "paid(u2) + paid(u3)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/remaining"]
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "H74"
title = "New timely proposal after an order change invalidated the old one"
category = "eligible"
rationale = """
An earlier proposal for u1 was created on time but stopped
being valid when the order record changed before payment.
Refund-policy/v2/validity requires a new proposal following
such an invalidation. Unlike a late request requiring staff
review under refund-policy/v2/window, the current request
is still comfortably within thirty days after delivery.
The present order qualifies, the unit has been received back,
and the customer can confirm a fresh proposal followed by
new staff approval and payment.
"""
now = "12 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 12 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Adjustable phone tripod"
returned = "received back 9 days before now"
discount = "none"

[[past_proposals]]
units = ["u1"]
status = "invalidated"
when = "created 7 days before now; invalidated 5 days before now when the order record was corrected, before payment"

[customer]
goal = "Get a fresh refund proposal for your returned phone tripod after an earlier proposal was invalidated by a correction to the order record."
opening_message = "The refund request for my phone tripod stopped being valid after a correction to the order details. I didn't cancel it, and no refund came through. Could you create a fresh one?"
facts = [
  { text = "The earlier proposal was invalidated after the order record changed.", reveal = "upfront" },
  { text = "The earlier proposal was never paid.", reveal = "upfront" },
  { text = "The current order record still shows one valid original payment and the returned unit.", reveal = "when_asked" }
]
behaviour = [
  "Ask for a new proposal rather than attempting to confirm the invalidated one.",
  "Do not claim that the previous proposal was paid.",
  "Confirm the new proposal for the tripod.",
  "Decline a person.",
  "End once the new refund receipt is given."
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u1"]
refund_amount = "paid(u1)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/validity"]
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "H75"
title = "Refund two nonconsecutive units from a discounted four-unit line"
category = "eligible"
rationale = """
The order contains four identical physical units with a discount
allocated when the order was recorded. Only u1 and u4 were
received back, in separate return shipments. Under
refund-policy/v2/amount, each unit retains its original paid
amount, including any centavo remainder allocated to later
units. The refund must equal paid(u1) + paid(u4), without
recalculating the discount across only the returned units.
The two kept units are not part of the request.
"""
now = "19 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 19 days before now"
shape = { items = 4, distinct_products = 1, sellers = 1, payments = ["boleto"] }

[[orders.units]]
key = "u1"
product = "Stackable glass food container"
returned = "received back 9 days before now"
discount = "listed 15% above what was paid; shared discount allocated across four identical units"

[[orders.units]]
key = "u2"
product = "Stackable glass food container"
returned = "not received back"
discount = "listed 15% above what was paid; shared discount allocated across four identical units"

[[orders.units]]
key = "u3"
product = "Stackable glass food container"
returned = "not received back"
discount = "listed 15% above what was paid; shared discount allocated across four identical units"

[[orders.units]]
key = "u4"
product = "Stackable glass food container"
returned = "received back 3 days before now"
discount = "listed 15% above what was paid; shared discount allocated across four identical units"

[customer]
goal = "Refund the first and last allocated units of four identical glass containers, both recorded as returned, while keeping the middle two."
opening_message = "I bought four identical glass food containers at a discount. I returned one earlier and another this week, and kept the other two. Please refund the two returned units using their actual discounted amounts."
facts = [
  { text = "The shop recorded the first and fourth allocated units as returned.", reveal = "upfront" },
  { text = "The two returns arrived in separate shipments.", reveal = "upfront" }
]
behaviour = [
  "Explain that only two of the four physical containers were returned.",
  "Accept the unit-level amounts stored on the order.",
  "Do not insist that every container must have an identically rounded refund.",
  "Confirm only u1 and u4.",
  "Decline a person.",
  "End after the refund receipt is provided."
]
confirms = { units = ["u1", "u4"], amount = "paid(u1) + paid(u4)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u1", "u4"]
refund_amount = "paid(u1) + paid(u4)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/amount"]
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "H76"
title = "Customer accepts a smaller refund after learning one item cannot be included yet"
category = "eligible"
rationale = """
The customer initially requests all three products, but the
shop has received only u1 and u2. The customer explicitly says
u3 is still at home and will be returned later. Under
refund-policy/v2/return, the unreceived u3 cannot be refunded
now. The agent explains this requirement, and the customer
voluntarily narrows the request to u1 and u2. Those units are
eligible for a proposal, confirmation, staff approval and
payment. No refund or handoff is required for u3.
"""
now = "13 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 13 days before now"
shape = { items = 3, distinct_products = 3, sellers = 2, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Stoneware dinner plate"
returned = "received back 5 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Ceramic soup bowl"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Glass dessert dish"
returned = "not received back"
discount = "none"

[customer]
goal = "Initially request refunds for all three products, then accept a refund for only the dinner plate and soup bowl after learning that the dessert dish must be returned first."
opening_message = "I'd like to refund three things from my order. You already received the dinner plate and soup bowl, but the glass dessert dish is still at home and I'll send it next week. Can you refund all three now?"
facts = [
  { text = "The dessert dish has not been sent back.", reveal = "upfront" },
  { text = "You are willing to refund the two received units now and request the dessert dish separately after its return.", reveal = "when_asked" }
]
behaviour = [
  "Initially request all three products.",
  "When told the dessert dish must arrive first, accept that it cannot be refunded now.",
  "Explicitly change the request to the dinner plate and soup bowl only.",
  "Confirm only the two-unit proposal.",
  "Decline a human handoff.",
  "End after the two-unit refund receipt is provided."
]
confirms = { units = ["u1", "u2"], amount = "paid(u1) + paid(u2)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u1", "u2"]
refund_amount = "paid(u1) + paid(u2)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/return"]
communication = ["states_correct_amount", "gives_this_receipt"]
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
last_proposal_status = ["none"]
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
last_proposal_status = ["none"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/payment"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H79"
title = "Shipping refund requested after the product refund was completed"
category = "clarification_handoff"
rationale = """
The only unit in the order was already refunded and has a
historical receipt. The customer now asks specifically for
the shipping charge, not another product refund. Under
refund-policy/v2/shipping, shipping charges are not
automatically refunded and a request to refund them requires
a person. The previous product refund remains paid and must
not be repeated or altered during the handoff.
"""
now = "22 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 22 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Metal desk drawer organiser"
returned = "received back 13 days before now"
discount = "none"

[[past_refunds]]
units = ["u1"]
when = "9 days before now"

[customer]
goal = "Get staff assistance with refunding the original shipping charge after the product refund has already been completed."
opening_message = "Thanks for refunding my desk organiser last week. I have the receipt for that. But the shipping charge wasn't included, and I'd like to ask for that back as well."
facts = [
  { text = "The product refund has already been completed.", reveal = "upfront" },
  { text = "You are asking for shipping(o1), not another refund of paid(u1).", reveal = "upfront" }
]
behaviour = [
  "Keep the request limited to shipping.",
  "Do not request another refund for the already-refunded organiser.",
  "Accept an explanation that shipping refunds require a staff member.",
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
handoff_origins = ["agent"]
cites = ["refund-policy/v2/shipping"]
communication = ["announces_handoff"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "H80"
title = "Completed refund followed by a request for human assistance"
category = "clarification_handoff"
rationale = """
The customer first completes an eligible refund for u1,
including proposal confirmation, staff approval and receipt.
Afterward, the customer explicitly requests a person about
a different order that is still being shipped. Under
refund-policy/v2/exceptions, the agent must honor the
customer's request for a person. A completed refund remains
paid after handoff; the agent must not reverse it, issue a
second refund or change anything once a person takes over.
"""
now = "10 days after o1 delivery and 4 days after o2 purchase"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 10 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Portable document scanner"
returned = "received back 3 days before now"
discount = "none"

[[orders]]
key = "o2"
owner = "customer"
status = "shipped"
timing = "purchased 4 days before now; shipped 2 days before now; not delivered"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["boleto"] }

[[orders.units]]
key = "u2"
product = "Laptop carrying sleeve"
returned = "not received back"
discount = "none"

[customer]
goal = "Complete the refund for your returned document scanner, receive its receipt, and then speak to a person about a separate still-shipped laptop sleeve order."
opening_message = "Could you refund the portable document scanner I returned? Let's finish that refund first, please."
facts = [
  { text = "You also have a separate shipped order that you want to discuss with a person after the scanner refund is complete.", reveal = "when_asked" }
]
behaviour = [
  "Initially discuss only the returned scanner.",
  "Confirm the correct scanner proposal through its card.",
  "After receiving the scanner refund receipt, say: 'Thank you. Now I'd like a real person to help me with my separate laptop sleeve order, which is still being shipped.'",
  "Do not request an automatic refund for the laptop sleeve.",
  "Do not ask for another scanner refund.",
  "End only after the person has been announced as taking over."
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u1"]
refund_amount = "paid(u1)"
last_proposal_status = ["refunded"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/exceptions"]
communication = ["states_correct_amount", "gives_this_receipt", "announces_handoff"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "H81"
title = "Customer requests a person after staff rejects a confirmed refund"
category = "clarification_handoff"
rationale = """
The customer confirms an eligible refund proposal, but the
staff member rejects it with a stated reason. Under
refund-policy/v2/approval, staff rejection prevents the
proposal from being paid and its reason must be communicated.
After receiving that decision, the customer explicitly asks
for a person. The agent must hand off while preserving the
rejected status and must not promise that human review will
overturn the rejection.
"""
now = "14 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 14 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["debit_card"] }

[[orders.units]]
key = "u1"
product = "USB-C docking station"
returned = "received back 4 days before now"
discount = "none"

[customer]
goal = "Request and confirm the docking station refund, then ask for a person to review the staff rejection after learning its reason."
opening_message = "I've returned my USB-C docking station. Could you process the refund for me?"
facts = [
  { text = "You want human assistance if the staff member rejects the request.", reveal = "when_asked" }
]
behaviour = [
  "Confirm the correct refund proposal.",
  "Wait for the staff decision.",
  "If staff rejects the proposal, ask for the exact rejection reason.",
  "After the reason is explained, say: 'I'd like to speak to a person about that rejection, please.'",
  "Do not ask the agent to execute the rejected proposal.",
  "End when a person is announced as taking over."
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "reject"
note = "Staff could not complete the required return verification because the inspection documentation for this request was incomplete."

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["rejected"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/approval"]
communication = ["reports_rejection_truthfully", "announces_handoff"]
forbidden = []
```

```toml
id = "H82"
title = "Customer cancels a confirmed proposal before requesting a person"
category = "clarification_handoff"
rationale = """
The customer confirms a refund proposal and then cancels it
using the proposal card before staff approval. Under
refund-policy/v2/approval, this cancellation is valid and
prevents the proposal from being paid. The customer subsequently
requests a person, so a handoff is required. The cancelled
proposal remains cancelled rather than becoming invalidated,
because it was already closed before the handoff.
"""
now = "11 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Electric hand mixer"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Confirm the hand mixer refund, cancel the confirmed proposal through its card before staff approval, and then request a person to discuss the situation."
opening_message = "I'd like a refund for the electric hand mixer I returned. Could you arrange that?"
facts = [
  { text = "After confirming the proposal, you decide to cancel it and ask for human assistance instead.", reveal = "when_asked" }
]
behaviour = [
  "Initially request a normal refund proposal.",
  "Confirm the correct proposal using its card.",
  "Cancel that confirmed proposal using its card before staff makes a decision.",
  "After cancellation, say: 'I've cancelled that proposal. I'd rather discuss the refund with a real person now.'",
  "Do not ask the agent to pay the cancelled proposal or create another one.",
  "End when a person is announced as taking over."
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "cancel" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["cancelled"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/approval"]
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
last_proposal_status = ["none", "cancelled"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/return"]
communication = ["announces_handoff"]
forbidden = []
```

```toml
id = "H84"
title = "Customer accepts human assistance for cancellation of a shipped order"
category = "clarification_handoff"
rationale = """
The order is still shipped and has not been delivered. Under
refund-policy/v2/eligible-orders, it cannot be refunded through
the refund process. Cancelling an undelivered order is outside
that process, and the agent may offer a person to help.
Unlike a customer who declines that offer, this customer
explicitly accepts it. The handoff is therefore required by
the customer's request, with no automatic refund.
"""
now = "6 days after o1 was purchased"

[[orders]]
key = "o1"
owner = "customer"
status = "shipped"
timing = "purchased 6 days before now; shipped 3 days before now; not delivered"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Portable desk humidifier"
returned = "not received back"
discount = "none"

[customer]
goal = "Find out whether your still-shipped humidifier can be refunded or cancelled, then accept assistance from a person for cancellation."
opening_message = "I ordered a portable desk humidifier, but I don't need it anymore. It hasn't arrived and still says shipped. Can I get a refund or cancel the order?"
facts = [
  { text = "The order has not been delivered.", reveal = "upfront" },
  { text = "You would like human help with cancellation if the agent cannot handle it directly.", reveal = "when_asked" }
]
behaviour = [
  "Acknowledge that the order is still in transit.",
  "If the agent explains that refunding an undelivered order is outside the process, accept that answer.",
  "When offered a staff member for cancellation, explicitly request the transfer.",
  "Do not insist on an automatic refund.",
  "End when a person is announced as taking over."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["explains_refusal_reason", "announces_handoff"]
forbidden = []
```

```toml
id = "H85"
title = "Customer requests a person after a late refund refusal"
category = "clarification_handoff"
rationale = """
The request is seven days beyond the thirty-day deadline, and
there is no earlier qualifying proposal. Under
refund-policy/v2/window, the refund must be refused as late.
A staff member cannot authorize an exception that violates
the policy. However, refund-policy/v2/exceptions also requires
a handoff whenever the customer explicitly asks for a person,
including after a refusal. The agent must explain the refusal
and then honor that separate request without promising approval.
"""
now = "37 days after o1 was delivered"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 37 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["debit_card"] }

[[orders.units]]
key = "u1"
product = "Cotton shower curtain"
returned = "received back 6 days before now"
discount = "none"

[customer]
goal = "Request the late shower curtain refund and, after learning that the policy refuses it, speak to a person anyway."
opening_message = "I know it's been a while, but I've returned the shower curtain and would like a refund. Could you check whether it's still possible?"
facts = [
  { text = "No earlier refund proposal was created for this unit.", reveal = "when_asked" },
  { text = "You want to speak to a person after receiving a refusal, even if staff cannot override the policy.", reveal = "when_asked" }
]
behaviour = [
  "Initially ask for the refund without requesting a person.",
  "If the agent explains that the thirty-day deadline has passed, accept that this refund is not allowed.",
  "Then say: 'I understand you can't approve an exception. I'd still like to speak to a person, please.'",
  "Do not demand that the agent promise the person can approve the refund.",
  "End when the handoff is announced."
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/window"]
communication = ["explains_refusal_reason", "announces_handoff"]
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
last_proposal_status = ["none"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders"]
communication = ["announces_handoff"]
forbidden = []
```
