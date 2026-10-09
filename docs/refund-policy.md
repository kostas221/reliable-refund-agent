# Refund policy (refund-policy/v1)

<!-- Generated from policies/refund-policy-v1.toml by `uv run python -m refund_agent.policy`. Do not edit by hand. -->

Demo policy of a fictional shop. Under each heading is the ID that a citation of that section carries.

## What this policy covers

`refund-policy/v1/scope`

This policy covers refunds for items in orders that the signed-in customer placed with the demo shop. All amounts are in
BRL. The shop and this policy are fictional: this is a demonstration, not the policy of any real shop and not legal
advice.

## Which orders qualify

`refund-policy/v1/eligible-orders`

Only orders with the status "delivered" can receive a refund. An order that has not been delivered is not refunded
through this process. If the customer reports a delivery that never arrived, a staff member takes the case.

## Time limit

`refund-policy/v1/window`

A refund must be requested within 30 days after the delivery time recorded on the order. The request time is the moment
the shop creates the refund proposal. If the proposal was created in time, a later confirmation, approval or payment of
that same proposal is still on time.

## Items must be returned first

`refund-policy/v1/return`

The shop refunds only units it has received back. The shop's own return records decide this, not a statement by the
customer or by the assistant. If the units have not arrived, the shop does not pay a refund for them and the assistant
explains why. If the customer says the units were already sent, a staff member checks.

## Refund amount

`refund-policy/v1/amount`

The refund for a unit is what the customer paid for it: its price minus any discount already allocated to that order
line. Shipping charges are not part of it. When only some units of a line are refunded, amounts are rounded down, so
refunds for a line never add up to more than was paid for it; the rounding remainder is refunded with the last unit of
the line.

## Earlier refunds count

`refund-policy/v1/remaining`

Earlier refunds reduce what is left. For each order line, the shop refunds at most the units that were paid for and
received back, and at most the amount paid, minus everything already refunded on that line. A request for more than what
is left is not paid; the assistant can offer what remains.

## Shipping charges

`refund-policy/v1/shipping`

Shipping charges are never refunded automatically. If the customer asks for shipping to be refunded, a staff member
takes the case.

## Where the money goes

`refund-policy/v1/payment`

A refund is paid only to the payment record that paid for the order. It cannot be sent to another person, account or
card. Orders paid with more than one payment record are handled by a staff member.

## Confirmation and approval

`refund-policy/v1/approval`

Every refund needs two separate decisions: the customer confirms the exact proposal (items, quantities and amount) with
the button on the proposal card, and a staff member approves it. Changing anything in a proposal needs a new proposal, a
new confirmation and a new approval. A staff member cannot approve a refund that this policy does not allow.

## How long a proposal is valid

`refund-policy/v1/validity`

A proposal is valid for 72 hours after it is created. If it has not been paid by then, it expires together with its
confirmation and approval, and a new proposal is needed. A proposal also stops being valid if the order or this policy
changes before it is paid.

## When the money is paid

`refund-policy/v1/payout`

The shop pays a refund only when all of these hold: the order qualifies, the request was on time, the units were
received back, the amount fits what is left, the customer confirmed, a staff member approved, and the proposal is still
valid. The refund is complete only when the customer has a receipt; until then nothing is reported as refunded.

## Exceptions and talking to a person

`refund-policy/v1/exceptions`

Anything this policy does not cover, and any request for an exception, goes to a staff member. The customer can ask for
a person at any time.
