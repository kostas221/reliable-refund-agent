# Refund policy (refund-policy/v2)

<!-- Generated from policies/refund-policy-v2.toml by `uv run python -m refund_agent.policy`. Do not edit by hand. -->

Demo policy of a fictional shop. Under each heading is the ID that a citation of that section carries.

## What this policy covers

`refund-policy/v2/scope`

This policy covers refunds for items in orders that the signed-in customer placed with the demo shop. All amounts are in
BRL, and all times are the shop's clock in UTC. The shop and this policy are fictional: this is a demonstration, not the
policy of any real shop and not legal advice.

## Which orders qualify

`refund-policy/v2/eligible-orders`

Only orders with the status "delivered" can receive a refund. An order that has not been delivered is not refunded
through this process: the assistant tells the customer the order's status, and cancelling the order or changing its
delivery is outside this process, so the assistant offers a staff member for that. If an order is recorded as delivered
but the customer says it never arrived, a staff member takes the case. If a delivered order has no delivery time, or one
that cannot be right (before the purchase or in the future), a staff member takes the case.

## Time limit

`refund-policy/v2/window`

A refund must be requested no later than 30 days after the delivery time recorded on the order. Days are exact periods
of twenty-four hours, and a request at exactly the deadline is on time. The request time is the moment the shop creates
the refund proposal. If an earlier proposal for the same units was created in time and then expired, or stopped being
valid because the order or this policy changed, before it was paid, a later request for those units is not refused for
being late: a staff member takes the case. A proposal that the customer replaced or cancelled, that a staff member
rejected, or that a handoff closed does not count. A request for an exception to the time limit is refused with this
reason.

## Items must be returned first

`refund-policy/v2/return`

The shop refunds only units it has received back, as shown by its own return records, never by a statement of the
customer or the assistant. If the records show the units arrived, the request continues normally. If they do not, the
shop pays nothing for those units: if the customer says the units were already sent, a staff member checks; if the
customer will send them later, the assistant explains that they must arrive first and requests nothing for them now.

## Refund amount

`refund-policy/v2/amount`

The refund for a unit is what was paid for that unit: its price minus its share of any discount. The shares are fixed
once, when the order is recorded, and never recalculated: when a paid total is split among identical units, each unit
gets the total divided by the number of units, rounded down to the smallest unit of the currency, and what is left over
is added one smallest unit at a time to the last units, so no unit is refunded more than its price. Shipping charges are
not part of the amount. A unit for which nothing was paid has nothing to refund: a request that includes it is refused,
and the other units can be requested without it. Nobody can raise the amount, so a request for more than was paid is
refused with this reason.

## Each unit is refunded once

`refund-policy/v2/remaining`

Each unit is refunded at most once, in full. A unit that was already refunded cannot be refunded again; the refund
already paid is reported with its receipt. A request for more units than are left is not paid; the assistant can offer
the units that remain.

## Shipping charges

`refund-policy/v2/shipping`

Shipping charges are never refunded automatically. If the customer asks for shipping to be refunded, a staff member
takes the case. A question about shipping charges is answered from this section.

## Where the money goes

`refund-policy/v2/payment`

A refund is paid automatically only when the order has exactly one payment record and that record is valid (a known
payment method and a positive amount), and only to that payment. Instalments of one payment are one payment record. When
the order has several payment records, or its one record is not valid, a staff member takes the case. A refund can never
be sent to another person, account or card: such a request is refused with this reason, and the refund can still go to
the original payment if the customer accepts. A customer's statement that the original card was cancelled does not
change where the refund goes; the card's issuer handles the credit, and the shop cannot promise where or when it
appears.

## Confirmation and approval

`refund-policy/v2/approval`

Every refund needs two separate decisions: the customer confirms the exact proposal (items, quantities and amount) with
the button on the proposal card, and a staff member approves it. A message in the chat confirms nothing. Until a
proposal is paid, the customer can cancel it with the button on its card; a message in the chat does not cancel it
either. Changing anything in a proposal needs a new proposal, a new confirmation and a new approval. A staff member
cannot approve a refund that this policy does not allow, and a staff member who rejects a proposal gives the reason,
which the customer is told.

## How long a proposal is valid

`refund-policy/v2/validity`

A proposal can be confirmed, approved or paid only strictly before it expires, 72 hours after it is created. After that
it expires together with its confirmation and approval, and a new proposal is needed. A proposal also stops being valid
if the order or this policy changes before it is paid. Expiry stops new payments only: a refund already paid stays paid,
and its receipt can always be retrieved.

## When the money is paid

`refund-policy/v2/payout`

The shop pays a refund only when all of these hold: the order qualifies, the request was on time, the units were
received back and not refunded before, the order has one valid payment, the customer confirmed, a staff member approved,
and the proposal is still valid. The refund is complete only when the customer has a receipt; until then nothing is
reported as refunded. In this demonstration a receipt records the refund in the shop's test ledger: it is not a bank
transfer, and the shop gives no date for the money to appear on a card.

## Exceptions and talking to a person

`refund-policy/v2/exceptions`

A person takes over the conversation when the customer asks for one, at any time; when the shop's decision on a request
is that a staff member takes the case; or in a case this policy names: units the customer says were sent but have not
arrived, a delivered order the customer says never arrived, and a request to refund shipping. A request for an exception
to a rule of this policy is refused with that rule's reason, because a staff member cannot approve a refund this policy
does not allow. A request one rule refuses does not become a staff case because of another rule: only the customer's
request for a person, or a case named above, makes it one. After a refusal the assistant gives the reason, and the
customer can still ask for a person. A question this policy does not answer, such as cancelling an order on its way, is
answered as far as the policy goes, and a person is offered, not imposed. When a person takes over, every proposal of
the conversation that is not paid is closed, and the person continues from there; a refund already paid stays paid.
