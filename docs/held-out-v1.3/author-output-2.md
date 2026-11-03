id = "H461"
title = "Past-deadline order with an earlier on-time invalidated proposal requires staff handoff and forbids simple late refusal"
category = "clarification_handoff"
novel = true
nearest = "D10"
difference = "Instead of an earlier expired proposal alone, the order is past 30 days after an earlier on-time proposal was invalidated by an order change, and the customer also asks about a second unit that was already refunded."
rationale = """
Under refund-policy/v2/window, if an earlier proposal for the same unit (u2) was created in time and stopped being valid because the order or policy changed before it was paid, a later request after 30 days is not refused for being late: a staff member takes the case. Under refund-policy/v2/remaining, u1 was already refunded once and its receipt is reported.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 34 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Ceramic soup tureen"
returned = "received back 20 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Porcelain gravy boat"
returned = "received back 18 days before now"
discount = "none"

[[past_refunds]]
units = ["u1"]
when = "16 days before now"

[[past_proposals]]
units = ["u2"]
status = "invalidated"
when = "12 days before now"

[customer]
goal = "Ask to refund your porcelain gravy boat (whose earlier on-time proposal stopped being valid when the order record changed) even though it is now 34 days after delivery, and also ask for the receipt of your already-refunded ceramic soup tureen."
opening_message = "Hi, I want to refund the porcelain gravy boat from my order delivered 34 days ago—my first proposal for it was made on time 12 days ago before it stopped being valid due to an order update. Could you also give me the receipt number for the ceramic soup tureen that was already refunded?"
facts = []
behaviour = [
"Accept the receipt for the soup tureen and the announcement that a staff member is taking over the gravy boat request, and end the conversation.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/window", "refund-policy/v2/remaining"]
quality_cites = ["refund-policy/v2/validity"]
communication = ["announces_handoff"]
forbidden = ["refused_as_simply_late"]

[expected.obligations]
"refund-policy/v2/window" = "Because an earlier proposal for the porcelain gravy boat was created in time and stopped being valid before payment, the late request is not refused for being past 30 days and a staff member takes the case."
"refund-policy/v2/remaining" = "The ceramic soup tureen was already refunded once and its existing receipt is reported."

id = "H462"
title = "Two orders: customer completes refund on one order, then reports that a second order paid with two payment methods is missing its return scan after being mailed"
category = "clarification_handoff"
novel = true
nearest = "D62"
difference = "After completing the refund on the first order, the customer asks to refund a second delivered order whose item they say was already mailed back (though shop records show not received back) and which also has two payment records, requiring a policy-mandated handoff under return."
rationale = """
Order o1 (u1) qualifies and is refunded with a receipt. In order o2, u2 is recorded as not received back, and because the customer says u2 was already sent back, a staff member checks under refund-policy/v2/return (and under refund-policy/v2/exceptions, the paid refund on o1 stays paid when the person takes over).
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Brass bookends"
returned = "received back 4 days before now"
discount = "none"

[[orders]]
key = "o2"
owner = "customer"
status = "delivered"
timing = "delivered 9 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card", "voucher"] }

[[orders.units]]
key = "u2"
product = "Leather desk blotter"
returned = "not received back"
discount = "none"

[customer]
goal = "First get a refund and receipt for your brass bookends, and once that refund is paid, ask to refund your leather desk blotter from your other order, explaining that you already mailed it back five days ago."
opening_message = "Hi, please refund the brass bookends I returned first."
facts = [
{ text = "After you receive the receipt for the brass bookends, you want to refund the leather desk blotter from your second order, which you already shipped back 5 days ago via postal drop-off.", reveal = "upfront" },
]
behaviour = [
"Confirm the proposal for u1 first and wait until the agent gives you the receipt.",
"After getting the receipt for u1, ask to refund the leather desk blotter (u2) and state that you already sent it back 5 days ago.",
"Accept the handoff to a staff member to check the return, and end the conversation.",
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"
note = ""

[expected]
refunded_units = ["u1"]
refund_amount = "paid(u1)"
last_proposal_status = ["refunded", "ineligible"]
handoff = "required"
handoff_origins = ["agent", "customer"]
cites = ["refund-policy/v2/return"]
quality_cites = ["refund-policy/v2/exceptions", "refund-policy/v2/payment"]
communication = ["proposes_without_asking", "states_correct_amount", "gives_this_receipt", "announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/return" = "Because the shop's return records do not show the leather desk blotter has arrived back yet and you state it was already sent, a staff member takes the case to check."

id = "H463"
title = "Ambiguous item across two returned units in an order paid with credit card and voucher: agent resolves ambiguity first, then hands off due to multiple payment records"
category = "clarification_handoff"
novel = true
nearest = "D29"
difference = "Unlike D29 where only one unit exists, the order has two returned cushions that both match the customer's words, so the agent must resolve ambiguity first before creating the proposal for the chosen unit that triggers the multi-payment staff handoff."
rationale = """
Because both u1 and u2 are returned velvet cushions matching the customer's opening request, the agent must ask which one is meant before proposing (resolves_ambiguity_first). Once the customer specifies u1, the order's two payment records (credit_card and voucher) require a staff member to take the case under refund-policy/v2/payment after an ineligible proposal.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 12 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card", "voucher"] }

[[orders.units]]
key = "u1"
product = "Emerald velvet cushion"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Sapphire velvet cushion"
returned = "received back 4 days before now"
discount = "none"

[customer]
goal = "Ask to refund 'the velvet cushion I returned', tell the agent you mean the emerald velvet cushion when asked, and accept when the case is sent to a staff member because you paid with both a credit card and a voucher."
opening_message = "Hi, I'd like a refund for the velvet cushion I returned."
facts = [
{ text = "You only want to refund the emerald velvet cushion (u1), not the sapphire one.", reveal = "when_asked" },
]
behaviour = [
"When the agent asks which velvet cushion you mean, specify the emerald velvet cushion (u1).",
"Once the agent explains that a staff member must take the case because the order has two payment records, accept the handoff and end the conversation.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/payment"]
quality_cites = []
communication = ["resolves_ambiguity_first", "announces_handoff"]
forbidden = ["proposal_with_other_units"]

[expected.obligations]
"refund-policy/v2/payment" = "Because the order has more than one payment record (a credit card and a voucher), the refund cannot be paid automatically and a staff member takes the case."

id = "H464"
title = "Three orders: one refused as late, one refused as unreturned, and one delivered order the customer says never arrived requiring staff handoff"
category = "clarification_handoff"
novel = true
nearest = "D51"
difference = "In addition to reporting that one delivered order never arrived, the customer has two other orders that must be refused under window (late) and return (not mailed yet) in the same conversation before handing off."
rationale = """
Order o1 (u1) was delivered 35 days ago with no prior proposal, so it is refused under refund-policy/v2/window. Order o2 (u2) has not been returned yet and the customer plans to mail it later, so it is refused under refund-policy/v2/return. Order o3 (u3) is recorded as delivered 6 days ago, but the customer states it never arrived, so a staff member takes the case under refund-policy/v2/eligible-orders.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 35 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Wicker storage basket"
returned = "received back 10 days before now"
discount = "none"

[[orders]]
key = "o2"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u2"
product = "Linen laundry liner"
returned = "not received back"
discount = "none"

[[orders]]
key = "o3"
owner = "customer"
status = "delivered"
timing = "delivered 6 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u3"
product = "Cedar coat hangers"
returned = "not received back"
discount = "none"

[customer]
goal = "Ask about all three of your orders at once: request a refund for your wicker storage basket delivered 35 days ago, request a refund for your linen laundry liner that you plan to mail back next week, and report that your cedar coat hangers order marked delivered 6 days ago never arrived at your house."
opening_message = "Hi! I need help with my three orders: I want a refund for my wicker storage basket, a refund for my linen laundry liner (which I'll mail back next week), and also my cedar coat hangers order says delivered 6 days ago but the package never arrived!"
facts = []
behaviour = [
"Accept the refusals for the wicker storage basket and the linen laundry liner, and accept the handoff to a staff member for the cedar coat hangers order that never arrived.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["agent", "customer"]
cites = ["refund-policy/v2/window", "refund-policy/v2/return", "refund-policy/v2/eligible-orders"]
quality_cites = []
communication = ["explains_refusal_reason", "announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/window" = "The wicker storage basket order was delivered more than 30 days ago, so a refund request for it is past the 30-day limit."
"refund-policy/v2/return" = "The linen laundry liner must be received back by the shop before it can be refunded."
"refund-policy/v2/eligible-orders" = "Because the cedar coat hangers order is recorded as delivered but you state it never arrived, a staff member takes the case."

id = "H465"
title = "Customer keeps initial single-unit proposal open (cards.other = wait), replaces it with a two-unit proposal, staff rejects, and customer asks for a person"
category = "clarification_handoff"
novel = true
nearest = "D79"
difference = "Unlike D79 where the conversation ends without handoff after the revised proposal is rejected, here the customer keeps the first card open with cards.other = wait, replaces it with a two-unit proposal that staff rejects, and then asks for a person."
rationale = """
Under refund-policy/v2/approval, changing a proposal from u1 to u1 and u2 requires a new proposal, confirmation, and staff approval, and when staff rejects the confirmed proposal, the customer is given the reason. Under refund-policy/v2/exceptions, when the customer then asks for a person, a person takes over.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 13 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Stoneware dinner plate"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Stoneware salad plate"
returned = "received back 4 days before now"
discount = "none"

[customer]
goal = "Start by asking to refund only the stoneware dinner plate, then once that card appears, ask to change the proposal to include both the dinner plate and the salad plate; after staff rejects the combined proposal, ask for a human agent."
opening_message = "Please create a refund proposal for my returned stoneware dinner plate."
facts = [
{ text = "Once the first proposal card for the dinner plate appears, you want to add the stoneware salad plate so both plates are refunded together, and you want to know what the rule is for changing a proposal.", reveal = "upfront" },
]
behaviour = [
"Wait for the proposal card for u1, then ask how changing a proposal works and ask to replace it with a proposal for both u1 and u2.",
"Confirm the combined proposal for u1 and u2.",
"When the agent tells you the staff member rejected the proposal, ask to speak to a human support person, accept the handoff, and end.",
]
confirms = { units = ["u1", "u2"], amount = "paid(u1) + paid(u2)" }
cards = { other = "wait", after_confirming = "keep" }

[staff]
decision = "reject"
note = "Both stoneware plates arrived cracked due to insufficient return packaging."

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["rejected"]
handoff = "required"
handoff_origins = ["customer"]
cites = ["refund-policy/v2/approval", "refund-policy/v2/exceptions"]
quality_cites = []
communication = ["states_correct_amount", "reports_rejection_truthfully", "announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/approval" = "Changing the items in a proposal requires a new proposal, confirmation, and approval, and when a staff member rejects a proposal, their reason is reported to the customer."
"refund-policy/v2/exceptions" = "A person takes over the conversation when the customer asks for one."

id = "H466"
title = "Order with one returned unit (already refunded) and one unreturned unit that customer claims was mailed back, plus request to refund shipping"
category = "clarification_handoff"
novel = true
nearest = "D40"
difference = "In addition to asking for a shipping refund after an earlier item refund, the order has a second unit that the customer claims was already mailed back (missing from return records) and the customer asks for the first unit's receipt."
rationale = """
Under refund-policy/v2/remaining, u1 was already refunded and its receipt is reported. Under refund-policy/v2/return, u2 is not shown as received back in shop records, and because the customer says it was already sent, a staff member checks. Under refund-policy/v2/shipping, the request to refund shipping also goes to a staff member.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Stainless colander"
returned = "received back 9 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Silicone splatter screen"
returned = "not received back"
discount = "none"

[[past_refunds]]
units = ["u1"]
when = "6 days before now"

[customer]
goal = "Ask for the receipt of your already-refunded stainless colander, ask to refund the silicone splatter screen which you mailed back 4 days ago, and also ask for the order's shipping charges to be refunded."
opening_message = "Hi! Can you give me the receipt for my stainless colander refund, and now refund both my silicone splatter screen (which I mailed back 4 days ago) and the shipping charges on the order?"
facts = [
{ text = "You dropped the silicone splatter screen off at the post office 4 days ago.", reveal = "upfront" },
]
behaviour = [
"Accept the receipt for the colander and the announcement that a staff member will take over to check the missing return and the shipping refund request.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["none", "ineligible"]
handoff = "required"
handoff_origins = ["agent", "customer"]
cites = ["refund-policy/v2/remaining", "refund-policy/v2/return", "refund-policy/v2/shipping"]
quality_cites = []
communication = ["announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/remaining" = "The stainless colander was already refunded once and its receipt is provided."
"refund-policy/v2/return" = "Because the shop's return records do not show the silicone splatter screen has arrived back and you state it was already sent, a staff member checks."
"refund-policy/v2/shipping" = "Shipping charges are never refunded automatically, so a staff member takes the case when a shipping refund is requested."

id = "H467"
title = "Delivered order recorded with a delivery time before purchase, combined with a customer question about a cancelled card"
category = "clarification_handoff"
novel = true
nearest = "D61"
difference = "Instead of a missing delivery timestamp, the order's recorded delivery time is before the purchase date, and the customer also asks what happens to a refund when the original credit card was cancelled."
rationale = """
Under refund-policy/v2/eligible-orders, if a delivered order has a delivery time that cannot be right (before the purchase), a staff member takes the case after an ineligible proposal. Under refund-policy/v2/payment, a cancelled card does not change where a refund goes; the card issuer handles the credit.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "bought 10 days before now, delivered 14 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Acoustic guitar stand"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Ask to refund your returned acoustic guitar stand, and also ask where the money goes since your original credit card was cancelled last week."
opening_message = "Hi, I want to refund the acoustic guitar stand I returned 3 days ago. By the way, the credit card I used for that order was cancelled last week—where does a refund go when a card is cancelled?"
facts = []
behaviour = [
"Accept the explanation about cancelled credit cards and the announcement that a staff member is taking over because the order's recorded delivery time is before the purchase date.",
]
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["ineligible"]
handoff = "required"
handoff_origins = ["agent"]
cites = ["refund-policy/v2/eligible-orders", "refund-policy/v2/payment"]
quality_cites = []
communication = ["announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/eligible-orders" = "Because the delivered order has a recorded delivery time that cannot be right (before the purchase), a staff member takes the case."
"refund-policy/v2/payment" = "A refund still goes to the original payment record even if the card was cancelled, and the card issuer handles the credit."

id = "H468"
title = "Customer confirms proposal, cancels it with the button after asking about discount share, and then asks for a person while a second order is shipped"
category = "clarification_handoff"
novel = true
nearest = "D78"
difference = "Instead of ending after cancelling a confirmed card over bank timing, the customer has a discounted item and a second shipped order, cancels the confirmed card with the button, and then asks for a person to help cancel the shipped order, requiring handoff."
rationale = """
Under refund-policy/v2/amount, the refund amount is the discounted price paid. Under refund-policy/v2/approval, the customer can cancel a confirmed proposal with the card button before it is paid. Under refund-policy/v2/eligible-orders and refund-policy/v2/exceptions, cancelling a shipped order is outside this process and a person takes over when requested/accepted.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Linen duvet cover"
returned = "received back 3 days before now"
discount = "listed 20% above what was paid"

[[orders]]
key = "o2"
owner = "customer"
status = "shipped"
timing = "bought 2 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u2"
product = "Down alternative comforter"
returned = "not received back"
discount = "none"

[customer]
goal = "Ask to refund your returned linen duvet cover and ask why the amount is less than the listed price, confirm the card and immediately cancel it with the card button, and then ask for a staff member to help cancel your shipped comforter order."
opening_message = "Please propose a refund for my returned linen duvet cover, and tell me why the refund amount is lower than its listed price."
facts = [
{ text = "After you confirm and then cancel the linen duvet cover proposal card with the button, you want to ask for a person to help cancel your shipped down alternative comforter order.", reveal = "upfront" },
]
behaviour = [
"Wait for the proposal card for u1, which the script will confirm and then cancel.",
"Once the card is cancelled, tell the agent you decided to cancel the duvet cover refund for now, and ask to be connected to a staff member to cancel your shipped down alternative comforter order (u2).",
"Accept the handoff and end the conversation.",
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "cancel" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["cancelled"]
handoff = "required"
handoff_origins = ["customer", "agent"]
cites = ["refund-policy/v2/amount", "refund-policy/v2/eligible-orders"]
quality_cites = ["refund-policy/v2/approval", "refund-policy/v2/exceptions"]
communication = ["states_correct_amount", "announces_handoff"]
forbidden = []

[expected.obligations]
"refund-policy/v2/amount" = "The refund for a unit is what was actually paid for it after subtracting its share of the discount."
"refund-policy/v2/eligible-orders" = "An order that is still shipped cannot be refunded or cancelled through this process, so a staff member handles that request."

id = "H469"
title = "Three delivered orders each containing a returned lamp: agent must resolve ambiguity across three orders, then answer a voucher payment question and complete the refund"
category = "clarification_handoff"
novel = true
nearest = "D33"
difference = "The customer has three orders (all containing returned lamps that fit the customer's words), an earlier expired proposal on the chosen lamp, and a voucher payment question requiring validity and payment citations."
rationale = """
Because all three orders contain a returned lamp matching "the lamp I returned", the agent must ask which one is meant before proposing (resolves_ambiguity_first). Once the customer specifies the brass floor lamp (u2 in o2), the agent explains that its earlier expired proposal requires a new proposal under refund-policy/v2/validity and that a single voucher payment is refunded automatically under refund-policy/v2/payment.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 22 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Ceramic bedside lamp"
returned = "received back 8 days before now"
discount = "none"

[[orders]]
key = "o2"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["voucher"] }
tie = "same category as o1, another product"

[[orders.units]]
key = "u2"
product = "Brass floor lamp"
returned = "received back 9 days before now"
discount = "none"

[[past_proposals]]
units = ["u2"]
status = "expired"
when = "5 days before now"

[[orders]]
key = "o3"
owner = "customer"
status = "delivered"
timing = "delivered 9 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }
tie = "same category as o1, another product"

[[orders.units]]
key = "u3"
product = "Industrial desk lamp"
returned = "received back 2 days before now"
discount = "none"

[customer]
goal = "Ask to refund 'the lamp I returned', clarify when asked that you mean the brass floor lamp from the order paid with a voucher, ask why your earlier proposal for it expired and whether voucher refunds happen automatically, and complete the refund."
opening_message = "Hi, I'd like to get a refund for the lamp I returned."
facts = [
{ text = "You have three orders with returned lamps, and you only want to refund the brass floor lamp (u2) from the order delivered 16 days ago.", reveal = "when_asked" },
]
behaviour = [
"When the agent asks which returned lamp you want to refund, specify the brass floor lamp (u2) and ask why its earlier proposal expired and whether a single voucher payment is refunded automatically.",
"Confirm the new proposal for u2, decline any human handoff, and finish once you get the receipt.",
]
confirms = { units = ["u2"], amount = "paid(u2)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"
note = ""

[expected]
refunded_units = ["u2"]
refund_amount = "paid(u2)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/validity", "refund-policy/v2/payment"]
quality_cites = []
communication = ["resolves_ambiguity_first", "states_correct_amount", "gives_this_receipt"]
forbidden = ["proposal_with_other_units"]

[expected.obligations]
"refund-policy/v2/validity" = "A proposal expires 72 hours after creation if not paid, requiring a new proposal."
"refund-policy/v2/payment" = "An order with a single valid voucher payment record is refunded automatically back to that voucher."

id = "H470"
title = "Ambiguous item among two returned units where staff rejects the confirmed proposal after clarification and customer accepts the rejection"
category = "clarification_handoff"
novel = true
nearest = "D09"
difference = "After the agent resolves ambiguity between two returned items and the customer confirms the chosen unit's proposal, the staff member rejects the proposal and the agent must report the rejection reason truthfully without a handoff."
rationale = """
Both u1 and u2 are returned leather wallets matching the customer's initial request, so the agent must ask which one is meant before proposing (resolves_ambiguity_first). After the customer specifies u1 and confirms its proposal, the staff member rejects it under refund-policy/v2/approval, and the agent reports the rejection reason to the customer.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 14 days before now"
shape = { items = 3, distinct_products = 3, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Brown leather bifold wallet"
returned = "received back 5 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Black leather cardholder wallet"
returned = "received back 5 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Canvas travel belt"
returned = "not received back"
discount = "none"

[customer]
goal = "Ask to refund 'the leather wallet I returned', specify the brown leather bifold wallet when asked, confirm the proposal, and accept the staff rejection reason when informed."
opening_message = "Hello, please refund the leather wallet I returned from my order."
facts = [
{ text = "You mean the brown leather bifold wallet (u1), not the black leather cardholder wallet.", reveal = "when_asked" },
]
behaviour = [
"When the agent asks which returned leather wallet you mean, specify the brown leather bifold wallet (u1).",
"Confirm the proposal for u1.",
"When the agent reports that the staff member rejected the proposal and explains why, accept the decision without asking for a human agent and end the conversation.",
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "reject"
note = "The brown leather bifold wallet showed heavy monogram embossing applied after purchase."

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["rejected"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/approval"]
quality_cites = []
communication = ["resolves_ambiguity_first", "states_correct_amount", "reports_rejection_truthfully"]
forbidden = ["proposal_with_other_units"]

[expected.obligations]
"refund-policy/v2/approval" = "Every refund requires staff approval after customer confirmation, and when a staff member rejects a proposal, their reason is passed on to the customer."

id = "H471"
title = "Ambiguous request across two returned items where one unit was already refunded: customer asks to clarify which unrefunded silk scarf is meant, then cancels confirmed card with button"
category = "clarification_handoff"
novel = true
nearest = "D31"
difference = "The order has three returned scarves (one already refunded before the conversation and two still unrefunded), and after the agent resolves ambiguity between the two remaining scarves and reports the prior receipt, the customer confirms and then cancels the card with the button."
rationale = """
Unit u1 was already refunded under refund-policy/v2/remaining (so its receipt is reported), leaving two returned scarves (u2 and u3) that both match the customer's request for "my other returned silk scarf". The agent must ask which of u2 or u3 is meant before proposing (resolves_ambiguity_first). Once u2 is proposed and confirmed, the customer cancels it with the card button under refund-policy/v2/approval.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 15 days before now"
shape = { items = 3, distinct_products = 3, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Crimson silk scarf"
returned = "received back 9 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Ivory silk scarf"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Navy silk scarf"
returned = "received back 4 days before now"
discount = "none"

[[past_refunds]]
units = ["u1"]
when = "7 days before now"

[customer]
goal = "Ask for the receipt of your already-refunded crimson silk scarf and ask to refund 'one of the other silk scarves I returned', specify the ivory silk scarf when asked, and then after confirming the card, cancel it with the card button and ask if button cancellation stops the payout."
opening_message = "Hi! Could you give me the receipt for my crimson silk scarf that was already refunded, and start a refund for one of the other silk scarves I returned?"
facts = [
{ text = "Between the ivory silk scarf and the navy silk scarf, you want to refund the ivory silk scarf (u2).", reveal = "when_asked" },
]
behaviour = [
"When the agent asks whether you mean the ivory silk scarf or the navy silk scarf, specify the ivory silk scarf (u2).",
"After the script confirms and then cancels the proposal card for u2 using the card button, ask the agent to confirm that cancelling with the card button before payout stops the refund.",
"Decline any offer of a human agent and end the conversation.",
]
confirms = { units = ["u2"], amount = "paid(u2)" }
cards = { other = "decline", after_confirming = "cancel" }

[staff]
decision = "none"
note = ""

[expected]
refunded_units = []
refund_amount = "0"
last_proposal_status = ["cancelled"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/remaining", "refund-policy/v2/approval"]
quality_cites = []
communication = ["resolves_ambiguity_first", "states_correct_amount"]
forbidden = ["proposal_with_other_units"]

[expected.obligations]
"refund-policy/v2/remaining" = "The crimson silk scarf was already refunded once and its receipt is reported."
"refund-policy/v2/approval" = "Until a proposal is paid, the customer can cancel it using the button on the proposal card."

id = "H472"
title = "Ambiguous item in an order nearing the 30-day deadline: customer clarifies which returned item is meant, then keeps single-unit card open (cards.other = wait) to add the second returned item"
category = "clarification_handoff"
novel = true
nearest = "D77"
difference = "After the agent resolves ambiguity first between two returned bowls near the 30-day cutoff and proposes the chosen bowl, the customer leaves that card open (cards.other = wait) and asks to replace it with a proposal covering both returned bowls."
rationale = """
Because both u1 and u2 are returned ceramic bowls matching the customer's ambiguous opening request, the agent must ask which one is meant before proposing (resolves_ambiguity_first). Once the agent proposes u1, the customer keeps the card open and asks to include u2 as well, requiring a new proposal for both u1 and u2 under refund-policy/v2/approval, created on time within the 30-day limit under refund-policy/v2/window.
"""

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 29 days and 12 hours before now"
shape = { items = 3, distinct_products = 3, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Blue ceramic ramen bowl"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Green ceramic ramen bowl"
returned = "received back 4 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Bamboo chopstick rest"
returned = "not received back"
discount = "none"

[customer]
goal = "First ask to refund 'the ceramic ramen bowl I returned' and ask if you are still on time for the 30-day deadline; specify the blue bowl when asked, and once the proposal card for the blue bowl appears, change your mind and ask for a new proposal covering both the blue and green ramen bowls."
opening_message = "Hi, I want to refund the ceramic ramen bowl I returned—and since my order was delivered 29 and a half days ago, is my request still on time?"
facts = [
{ text = "When first asked which ceramic ramen bowl you mean, say you only want to refund the blue ceramic ramen bowl (u1).", reveal = "when_asked" },
{ text = "Once the proposal card for the blue bowl (u1) appears, you decide you want to refund both the blue and green ceramic ramen bowls (u1 and u2) together before the deadline expires, and ask how changing a proposal works.", reveal = "upfront" },
]
behaviour = [
"First answer the agent's clarifying question by naming only the blue ceramic ramen bowl (u1).",
"After the agent creates the proposal card for u1 alone, ask to change the proposal to include both the blue ceramic ramen bowl (u1) and the green ceramic ramen bowl (u2), and ask if changing items requires a new proposal.",
"Confirm the new proposal for u1 and u2, decline any offer of a human agent, and finish once you have the receipt.",
]
confirms = { units = ["u1", "u2"], amount = "paid(u1) + paid(u2)" }
cards = { other = "wait", after_confirming = "keep" }

[staff]
decision = "approve"
note = ""

[expected]
refunded_units = ["u1", "u2"]
refund_amount = "paid(u1) + paid(u2)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/window", "refund-policy/v2/approval"]
quality_cites = []
communication = ["resolves_ambiguity_first", "states_correct_amount", "gives_this_receipt"]
forbidden = []

[expected.obligations]
"refund-policy/v2/window" = "A refund request created within 30 days (24-hour periods) of the recorded delivery time is on time."
"refund-policy/v2/approval" = "Adding the second bowl to the proposal requires creating a new proposal, a new customer confirmation, and a new staff approval."
