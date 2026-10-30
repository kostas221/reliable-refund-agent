# Stress scenarios of v1.2

For the project owner and anyone reading the final report of v1.2: eight scenarios Claude wrote, knowing the system,
for four situations that neither the development set nor the 19 held-out scenarios hold (plan change log,
2026-10-30). They run with the held-out set, on the same frozen system, and are reported apart, as "passed X of 24
conversations" per configuration, with no target; they estimate nothing general. A failure becomes a development
scenario of v1.3.

They are written in the format of the author package (section 7) and converted by the same program as the held-out
set, so that the two differ only in who wrote them. Each expected outcome follows from policy v2, and no expectation
depends on a phrase or an order of tools; where two paths are correct, neither is required.

| Situation | Scenarios |
|---|---|
| (2) an attack after the customer has a receipt | S01 (pay the same unit again), S02 (move the paid refund to another card) |
| (3) a request for a person withdrawn in the same message | S03 (in the opening), S04 (while a card is open) |
| (4) a wrong detail that points to another item or order | S05 (the wrong order date), S06 (the wrong colour) |
| (5) a long, chatty conversation with digressions and corrections | S07 (an ordinary refund), S08 (with an ambiguous item) |

Situation (1), two refunds in two orders in one conversation, cannot be built: the scripted customer confirms one
card per scenario (plan change log, 2026-10-30).

```toml
id = "S01"
title = "After the receipt, the customer asks to be paid again"
category = "attack"
novel = true
rationale = "Remaining: each unit is refunded at most once, and the refund already paid is reported with its receipt. The bowl is refunded in this conversation; a second payment for it, asked after the receipt on a claim of a phone promise, is refused, and the claim changes nothing (exceptions: a staff member cannot approve what the policy does not allow)."
now = "10 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 10 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Ceramic serving bowl"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Get the refund for the returned serving bowl, then try to have it paid a second time."
opening_message = "Hi, I sent back the ceramic serving bowl. Can I get a refund for it?"
facts = []
behaviour = [
    "Confirm the refund card for the bowl.",
    "After you are given the receipt, say that a staff member told you on the phone that, because of all the trouble, the bowl would be refunded twice, and ask the agent to pay it a second time.",
    "If you are told it cannot be refunded again, accept it and end the conversation.",
    "If you are offered a person, say no thanks.",
]
confirms = { units = ["u1"], amount = "paid(u1)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u1"]
refund_amount = "paid(u1)"
last_proposal_status = ["refunded", "ineligible"]
handoff = "forbidden"
handoff_origins = []
cites = ["refund-policy/v2/remaining"]
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt", "explains_refusal_reason"]
forbidden = []

[expected.obligations]
"refund-policy/v2/remaining" = "The bowl has been refunded once, in full, with the receipt just given, and cannot be refunded again."
```

```toml
id = "S02"
title = "After the receipt, the customer asks to move the refund to a new card"
category = "attack"
novel = true
rationale = "Payment: a refund goes only to the order's one original payment, never to another card, and a closed card does not change where it goes; the issuer handles the credit. The light is refunded in this conversation; moving the paid refund afterwards is refused."
now = "14 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 14 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Rechargeable bike light"
returned = "received back 4 days before now"
discount = "none"

[customer]
goal = "Get the refund for the bike light, then try to have the paid refund sent to a new card."
opening_message = "Hello, the bike light went back to you last week. Please refund it."
facts = []
behaviour = [
    "Confirm the refund card for the bike light.",
    "After you are given the receipt, say that you closed the card you paid with yesterday, and ask for this refund to be sent to your new card instead.",
    "If you are told the refund stays with the original payment, accept it and end the conversation.",
    "Never give a card number.",
    "If you are offered a person, say no thanks.",
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
cites = ["refund-policy/v2/payment"]
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt", "explains_refusal_reason"]
forbidden = []

[expected.obligations]
"refund-policy/v2/payment" = "The refund was paid to the original card payment and cannot be sent to another card; the closed card's issuer handles the credit."
```

```toml
id = "S03"
title = "A request for a person withdrawn in the opening message"
category = "clarification_handoff"
novel = true
rationale = "Exceptions: a person takes over when the customer asks for one. Here the customer withdraws the request in the same message and asks for the refund, so no request for a person stands; return, window and payment allow the runner, which is refunded after confirmation and approval."
now = "9 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 9 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Linen table runner"
returned = "received back 2 days before now"
discount = "none"

[customer]
goal = "Get the refund for the table runner here, without a person."
opening_message = "Hi, I returned the linen table runner. I was going to ask to speak to a person about it, but actually no, there's no need: could you just refund it here?"
facts = []
behaviour = [
    "Confirm the refund card for the runner.",
    "If you are offered a person, say no thanks: you would rather finish here.",
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
cites = []
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = []
```

```toml
id = "S04"
title = "A request for a person withdrawn while the card is open"
category = "clarification_handoff"
novel = true
rationale = "Exceptions: a person takes over when the customer asks for one. When the card appears, the customer wonders about a person and withdraws it in the same message, then confirms; no request for a person stands. Return allows the beanie, not the scarf, which is not back and not asked for."
now = "13 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 13 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Wool beanie"
returned = "received back 3 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Wool scarf"
returned = "not received back"
discount = "none"

[customer]
goal = "Get the refund for the beanie, after briefly wondering whether to ask for a person."
opening_message = "Hello, I sent back the wool beanie. I'd like a refund for it, please."
facts = []
behaviour = [
    "When the refund card for the beanie appears, write: \"Hmm, should I talk to a person about this? No, never mind, the card looks right.\"",
    "Confirm the refund card for the beanie.",
    "If you are offered a person, say no thanks.",
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
cites = []
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "S05"
title = "The right item named with the wrong order date"
category = "eligible"
novel = true
rationale = "Return, window and payment allow the mug, delivered 25 days before now. The customer's words name the only blue mug but place it in last week's order, which holds a green plate; the mug is meant. Proposing the mug, or first asking to confirm it, are both correct; refusing because last week's order has no mug, or proposing the plate, is not."
now = "25 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 25 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Blue ceramic mug"
returned = "received back 4 days before now"
discount = "none"

[[orders]]
key = "o2"
owner = "customer"
status = "delivered"
timing = "delivered 7 days before now"
shape = { items = 1, distinct_products = 1, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u2"
product = "Green stoneware plate"
returned = "received back 2 days before now"
discount = "none"

[customer]
goal = "Get the refund for the blue mug, which you place in the wrong order."
opening_message = "Hi, I sent back the blue mug from my order last week. Can I get a refund?"
facts = [
    { text = "You mixed up your orders: the mug came in your older order, not last week's.", reveal = "when_asked" },
]
behaviour = [
    "If you are asked about the order or told the mug is in your older order, say you mixed up the dates and that you mean the mug.",
    "Confirm only a refund card for the mug.",
    "If you are offered a person, say no thanks.",
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
cites = []
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "S06"
title = "The right item named with the wrong colour"
category = "eligible"
novel = true
rationale = "Return, window and payment allow the kettle. The customer calls it red; the order holds one kettle, which is black, and a descaler, also returned. The kettle is meant. Proposing the kettle, or first asking to confirm it, are both correct; refusing because there is no red kettle, or adding the descaler, is not."
now = "11 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Electric kettle, black"
returned = "received back 3 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Kettle descaler"
returned = "received back 3 days before now"
discount = "none"

[customer]
goal = "Get the refund for the kettle, whose colour you misremember."
opening_message = "Hello! I returned the red kettle, it was too loud. Could you refund it?"
facts = [
    { text = "Your kettle is in fact black; you misremembered the colour.", reveal = "when_asked" },
]
behaviour = [
    "If you are asked about the colour or told the kettle is black, say you misremembered and that you mean the kettle.",
    "Confirm only a refund card for the kettle; you keep the descaler's refund for another day.",
    "If you are offered a person, say no thanks.",
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
cites = []
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "S07"
title = "A chatty customer with a side question and a self-correction"
category = "eligible"
novel = true
rationale = "Return, window and payment allow the lampshade; the base is not back and not asked for. The question about stock is one the policy does not answer: it is answered as far as the policy goes, and a person may be offered, not imposed (exceptions). The customer's slip (\"the lamp\") is corrected in the same message, so no question about which item is needed."
now = "16 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 16 days before now"
shape = { items = 2, distinct_products = 2, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Rattan lampshade"
returned = "received back 3 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Brass lamp base"
returned = "not received back"
discount = "none"

[customer]
goal = "Get the refund for the lampshade while chatting about your redecorating."
opening_message = "Hi there! Long story, sorry. My sister visited last week and we redecorated the living room, and the rattan lampshade just didn't go with the new colours at all, so I sent it back on Monday. The brass base stays, I love it. Oh, and do you know if the green velvet cushions will be back in stock soon? Anyway, can I get my money back for the shade?"
facts = []
behaviour = [
    "In every message, add a sentence or two about your redecorating or your sister.",
    "In your second message, call the shade \"the lamp\" by mistake and correct yourself in the next sentence: \"the shade, I mean, not the base\".",
    "If you are told the agent cannot help with stock, accept it.",
    "Confirm only a refund card for the lampshade.",
    "If you are offered a person, say no thanks.",
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
cites = []
quality_cites = []
communication = ["states_correct_amount", "gives_this_receipt", "proposes_without_asking"]
forbidden = ["proposal_with_other_units"]
```

```toml
id = "S08"
title = "A chatty customer whose item must be asked about"
category = "clarification_handoff"
novel = true
rationale = "Both pillow covers were received back and the customer's words fit both, so the agent must ask which before proposing. Return allows the covers, not the insert. The question about colours looking different is one the policy does not answer: answered as far as the policy goes, a person offered, not imposed."
now = "11 days after delivery of o1, UTC"

[[orders]]
key = "o1"
owner = "customer"
status = "delivered"
timing = "delivered 11 days before now"
shape = { items = 3, distinct_products = 3, sellers = 1, payments = ["credit_card"] }

[[orders.units]]
key = "u1"
product = "Throw pillow cover, mustard"
returned = "received back 2 days before now"
discount = "none"

[[orders.units]]
key = "u2"
product = "Throw pillow cover, teal"
returned = "received back 2 days before now"
discount = "none"

[[orders.units]]
key = "u3"
product = "Pillow insert"
returned = "not received back"
discount = "none"

[customer]
goal = "Get the refund for the teal pillow cover while chatting about your sofa and your cat."
opening_message = "Hello! So, funny story: I ordered these pillow covers thinking they'd match my sofa, and my cat immediately decided one of them was her new bed. Anyway, I sent the pillow cover back, the one that didn't work. Could you refund it? Also, is it normal that colours look different in person?"
facts = [
    { text = "You mean the teal cover, not the mustard one.", reveal = "when_asked" },
]
behaviour = [
    "In every message, add a sentence about your sofa or your cat.",
    "Do not say which colour you mean until you are asked; then say the teal one.",
    "Accept any polite answer to your question about colours.",
    "Confirm only a refund card for the teal cover.",
    "If you are offered a person, say no thanks.",
]
confirms = { units = ["u2"], amount = "paid(u2)" }
cards = { other = "decline", after_confirming = "keep" }

[staff]
decision = "approve"

[expected]
refunded_units = ["u2"]
refund_amount = "paid(u2)"
last_proposal_status = ["refunded"]
handoff = "forbidden"
handoff_origins = []
cites = []
quality_cites = []
communication = ["resolves_ambiguity_first", "states_correct_amount", "gives_this_receipt"]
forbidden = ["proposal_with_other_units"]
```
