# The Olist subset

`subset.json` holds 23 real orders, drawn for the 20 held-out scenarios, from the **Brazilian E-Commerce Public
Dataset by Olist**: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce, published by Olist on Kaggle under
**CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/). This folder, and every scenario fixture
that copies numbers from it, is under that licence, not under the licence of the code: it may be shared and adapted
for non-commercial use, with this attribution, under the same licence. The original files stay out of git, in
`data/raw/olist/`.

## Provenance

- Downloaded from the Kaggle page above on 2026-10-18; the dataset says it is never updated. The SHA-256 of each file
  used is recorded in `refund_agent/olist.py`, which refuses files that differ.
- The dataset: about 100,000 orders from 2016 to 2018 at several Brazilian marketplaces, anonymised by Olist, in
  nine CSV files. Six are read: orders, order items, payments, products, product category names, and customers (only
  to tell whether two orders belong to one person). Reviews, sellers' cities and geolocation are not used.
- `uv run python -m refund_agent.olist` writes `subset.json` again, the same every time.

## How the orders were drawn

For each held-out situation (`docs/scenarios.md`), the orders of the shape it needs: for example delivered, two
items of two products from two sellers, one card payment (H01), or the same product bought by two customers (H16).
Orders whose payments do not equal their items and freight to the centavo are left out (315 single-card orders,
likely instalment interest), since the refund policy does not say how such interest is refunded. Among the orders
that fit, the one taken is the first by the SHA-256 of the situation's ID and the order ID, and no order is taken
twice: a fixed draw, not a choice. Each situation's line in the output gives how many orders fitted.

## What is real and what is synthetic

| From Olist, unchanged | Synthetic, written in the scenario |
|---|---|
| The order's items, which are the same product, each item's seller and category, prices, freight, payment records (method, instalments, amount), order status, and the days between purchase and delivery | Product names (Olist gives none, only a category), customer names and emails, return records, earlier refunds and proposals, list prices above what was paid (H02), and the dates: each order's dates are moved as one block to 2026, keeping their intervals |

Olist's order, product and seller IDs are kept in `subset.json` for provenance; the scenarios use their own IDs and
note the Olist order each fixture comes from.

## The held-out set of v1.1

`subset-v1.1.json` holds 21 more orders, drawn on 2026-10-25 for the 20 scenarios of `scenarios/held-out-v1.1/`
(`docs/held-out-v1.1/`) by `uv run python -m refund_agent.olist v1.1`: the shapes the author of those scenarios
stated, the same lot (the SHA-256 of the scenario's ID and the order ID), and never an order of `subset.json`. Its
records also keep the delivery date Olist promised at purchase (`estimated_delivery_at`), which times the one order
recorded as delivered with no delivery time (H77). What is real and what is synthetic is as above; how each order was
placed in time is in `docs/held-out-v1.1/conversion-log.md`. The same licence applies.
