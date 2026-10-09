# Refund policy (refund-policy/v1)

<!-- Generated from policies/refund-policy-v1.toml by `uv run python -m refund_agent.policy`. Do not edit by hand. -->

Demo policy of a fictional shop. Under each heading is the ID that a citation of that section carries.

## What this policy covers

`refund-policy/v1/scope`

This policy covers refunds for items in orders that the signed-in customer placed with the demo shop. All amounts are in
BRL, and all times are the shop's clock in UTC. The shop and this policy are fictional: this is a demonstration, not the
policy of any real shop and not legal advice.

## Which orders qualify

`refund-policy/v1/eligible-orders`

Only orders with the status "delivered" can receive a refund. An order that has not been delivered is not refunded
through this process; if the customer reports a delivery that never arrived, a staff member takes the case. If a
delivered order has no delivery time, or one that cannot be right (before the purchase or in the future), a staff member
takes the case.

## Time limit

`refund-policy/v1/window`

A refund must be requested no later than 30 days after the delivery time recorded on the order. Days are exact periods
of twenty-four hours, and a request at exactly the deadline is on time. The request time is the moment the shop creates
the refund proposal. If an earlier proposal for the same items was created in time but expired or stopped being valid
before it was paid, a later request is not refused for being late: a staff member takes the case.

## Items must be returned first

`refund-policy/v1/return`

The shop refunds only units it has received back, as shown by its own return records, never by a statement of the
customer or the assistant. If the records show the units arrived, the request continues normally. If they do not, the
shop pays nothing for those units; if the customer says the units were already sent, a staff member checks.

## Refund amount

`refund-policy/v1/amount`

The refund for a unit is what was paid for that unit: its price minus its share of any discount. The shares are fixed
once, when the order is recorded, and never recalculated: when a paid total is split among identical units, each unit
gets the total divided by the number of units, rounded down to the smallest unit of the currency, and what is left over
is added one smallest unit at a time to the last units, so no unit is refunded more than its price. Shipping charges are
not part of the amount.

## Each unit is refunded once

`refund-policy/v1/remaining`

Each unit is refunded at most once, in full. A unit that was already refunded cannot be refunded again. A request for
more units than are left is not paid; the assistant can offer the units that remain.

## Shipping charges

`refund-policy/v1/shipping`

Shipping charges are never refunded automatically. If the customer asks for shipping to be refunded, a staff member
takes the case.

## Where the money goes

`refund-policy/v1/payment`

A refund is paid automatically only when the order has exactly one payment record and that record is valid (a known
payment method and a positive amount), and only to that payment. Instalments of one payment are one payment record. In
every other case a staff member takes the case. A refund can never be sent to another person, account or card.

## Confirmation and approval

`refund-policy/v1/approval`

Every refund needs two separate decisions: the customer confirms the exact proposal (items, quantities and amount) with
the button on the proposal card, and a staff member approves it. Changing anything in a proposal needs a new proposal, a
new confirmation and a new approval. A staff member cannot approve a refund that this policy does not allow.

## How long a proposal is valid

`refund-policy/v1/validity`

A proposal can be confirmed, approved or paid only strictly before it expires, 72 hours after it is created. After that
it expires together with its confirmation and approval, and a new proposal is needed. A proposal also stops being valid
if the order or this policy changes before it is paid. Expiry stops new payments only: a refund already paid stays paid,
and its receipt can always be retrieved.

## When the money is paid

`refund-policy/v1/payout`

The shop pays a refund only when all of these hold: the order qualifies, the request was on time, the units were
received back and not refunded before, the order has one valid payment, the customer confirmed, a staff member approved,
and the proposal is still valid. The refund is complete only when the customer has a receipt; until then nothing is
reported as refunded.

## Exceptions and talking to a person

`refund-policy/v1/exceptions`

Anything this policy does not cover, and any request for an exception, goes to a staff member. The customer can ask for
a person at any time.
