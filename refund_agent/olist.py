"""The Olist subset behind the held-out scenarios: `uv run python -m refund_agent.olist [v1.1]` (plan section 6, data).

Reads the Kaggle files in data/raw/olist/ (never committed), refuses them unless each matches the SHA-256 recorded
below, and draws, for each held-out situation, real orders of the shape it needs. The draw is fixed, not chosen:
the orders that fit are ordered by the SHA-256 of the situation's ID and the order ID, and the first not drawn for
another situation is taken. It writes data/olist/subset.json, which the held-out fixtures copy their numbers from;
data/olist/README.md records the source, the licence and what is real and what is synthetic.

Taken from Olist: an order's items, which of them are the same product, each item's seller and category, prices,
freight, payment records, status, and how long delivery took. Synthetic: product and customer names, return
records, refunds, and the dates, moved to 2026 with their intervals kept. Orders whose payments do not add up to
their items and freight are left out: the refund policy does not say how instalment interest is refunded.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from refund_agent.policy import REPO_ROOT

RAW = REPO_ROOT / "data" / "raw" / "olist"
SUBSET = REPO_ROOT / "data" / "olist" / "subset.json"
SOURCE = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
LICENCE = "CC BY-NC-SA 4.0"
# The files as downloaded on 2026-10-18 (the dataset says it is never updated).
FILES = {
    "olist_customers_dataset.csv": "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2",
    "olist_order_items_dataset.csv": "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279",
    "olist_order_payments_dataset.csv": "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0",
    "olist_orders_dataset.csv": "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf",
    "olist_products_dataset.csv": "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc",
    "product_category_name_translation.csv": "a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278",
}


@dataclass
class Order:
    id: str
    customer: str  # Olist's customer_unique_id, used only to find two orders of one person
    status: str
    purchased_at: str
    delivered_at: str
    items: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)
    # The delivery date Olist promised at purchase: for v1.1, the one interval an order without a delivery time keeps.
    estimated_at: str = ""

    @property
    def products(self) -> int:
        return len({i["product_id"] for i in self.items})

    @property
    def sellers(self) -> int:
        return len({i["seller_id"] for i in self.items})

    @property
    def payment_types(self) -> list[str]:
        return sorted(p["payment_type"] for p in self.payments)

    def adds_up(self) -> bool:
        """The payments equal the items and their freight, to the centavo."""
        owed = sum(cents(i["price"]) + cents(i["freight_value"]) for i in self.items)
        return owed == sum(cents(p["payment_value"]) for p in self.payments)


def cents(value: str) -> int:
    reais, _, centavos = value.partition(".")
    return int(reais) * 100 + int((centavos + "00")[:2])


def sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(name: str) -> list[dict]:
    with open(RAW / name, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load() -> dict[str, Order]:
    wrong = [name for name, expected in FILES.items() if sha256(RAW / name) != expected]
    if wrong:
        sys.exit(f"These files differ from the recorded download: {wrong}")
    customers = {c["customer_id"]: c["customer_unique_id"] for c in read("olist_customers_dataset.csv")}
    english = {
        r["product_category_name"]: r["product_category_name_english"]
        for r in read("product_category_name_translation.csv")
    }
    category = {
        p["product_id"]: english.get(p["product_category_name"], p["product_category_name"] or "unknown")
        for p in read("olist_products_dataset.csv")
    }
    orders = {
        o["order_id"]: Order(
            o["order_id"],
            customers[o["customer_id"]],
            o["order_status"],
            o["order_purchase_timestamp"],
            o["order_delivered_customer_date"],
            estimated_at=o["order_estimated_delivery_date"],
        )
        for o in read("olist_orders_dataset.csv")
    }
    for item in read("olist_order_items_dataset.csv"):
        orders[item["order_id"]].items.append({**item, "category": category[item["product_id"]]})
    for payment in read("olist_order_payments_dataset.csv"):
        orders[payment["order_id"]].payments.append(payment)
    for order in orders.values():
        order.items.sort(key=lambda i: int(i["order_item_id"]))
        order.payments.sort(key=lambda p: int(p["payment_sequential"]))
    return orders


# What each held-out situation needs (docs/scenarios.md). A second order, when there is one, may be tied to the
# first: the same category with another product (similar items), or the same product for another customer.

Fits = Callable[[Order], bool]


def delivered(items: int = 1, products: int | None = None, sellers: int | None = None, pays=("credit_card",)) -> Fits:
    def fits(o: Order) -> bool:
        return (
            o.status == "delivered"
            and bool(o.delivered_at)
            and len(o.items) == items
            and (products is None or o.products == products)
            and (sellers is None or o.sellers == sellers)
            and o.payment_types == sorted(pays)
            and o.adds_up()
        )

    return fits


def in_transit(o: Order) -> bool:
    return o.status == "shipped" and len(o.items) == 1 and o.payment_types == ["credit_card"] and o.adds_up()


ONE_ITEM = delivered()
SITUATIONS: dict[str, tuple[Fits, ...]] = {
    "H01": (delivered(2, products=2, sellers=2),),
    "H02": (delivered(2, products=2, sellers=1),),
    "H03": (delivered(3, products=3),),
    "H04": (ONE_ITEM,),
    "H05": (ONE_ITEM, in_transit),
    "H06": (delivered(3, products=1, sellers=1),),
    "H07": (ONE_ITEM, ONE_ITEM),  # the second: the same category, another product
    "H08": (delivered(2, products=2),),
    "H09": (in_transit,),
    "H10": (delivered(2, products=2),),
    "H11": (ONE_ITEM,),
    "H12": (ONE_ITEM,),
    "H13": (ONE_ITEM,),
    "H14": (ONE_ITEM,),
    "H15": (delivered(2, products=2),),
    "H16": (ONE_ITEM, ONE_ITEM),  # the second: the same product, bought by another customer
    "H17": (ONE_ITEM,),
    "H18": (ONE_ITEM,),
    "H19": (delivered(1, pays=("credit_card", "voucher")),),
    "H20": (ONE_ITEM,),
}
TIED = {
    "H07": lambda first, o: (
        o.items[0]["category"] == first.items[0]["category"]
        and o.items[0]["product_id"] != first.items[0]["product_id"]
    ),
    "H16": lambda first, o: o.items[0]["product_id"] == first.items[0]["product_id"] and o.customer != first.customer,
}


# The held-out set of v1.1 (docs/held-out-v1.1/protocol.md, section 4.1): the shapes of the 20 candidates kept from
# the author's answers (docs/held-out-v1.1/set-aside.md, section 10), as each candidate states them. Drawn by the
# same lot, never an order of v1's subset.


def card_in_instalments(count: int) -> Fits:
    """One delivered item paid by one card payment in this many instalments (H29: the customer says three)."""
    one = delivered()
    return lambda o: one(o) and int(o.payments[0]["payment_installments"]) == count


def delivered_without_time(o: Order) -> bool:
    """Recorded as delivered with no delivery time (H77), one item, one card payment."""
    return (
        o.status == "delivered"
        and not o.delivered_at
        and len(o.items) == 1
        and o.payment_types == ["credit_card"]
        and o.adds_up()
    )


def in_transit_paid_by(pays: tuple[str, ...]) -> Fits:
    return lambda o: o.status == "shipped" and len(o.items) == 1 and o.payment_types == sorted(pays) and o.adds_up()


DEBIT, BOLETO = delivered(pays=("debit_card",)), delivered(pays=("boleto",))
SITUATIONS_V1_1: dict[str, tuple[Fits, ...]] = {
    "H26": (DEBIT,),
    "H28": (ONE_ITEM,),
    "H29": (card_in_instalments(3),),
    "H30": (delivered(3, products=3, sellers=2, pays=("boleto",)),),
    "H35": (delivered(3, products=1, sellers=1),),
    "H40": (ONE_ITEM,),
    "H41": (BOLETO,),
    "H42": (ONE_ITEM,),
    "H47": (ONE_ITEM,),
    "H50": (DEBIT,),
    "H52": (delivered(2, products=2, sellers=2, pays=("voucher",)),),
    "H55": (DEBIT,),
    "H58": (BOLETO,),
    "H60": (delivered(3, products=3, sellers=2),),
    "H61": (DEBIT,),
    "H63": (ONE_ITEM,),
    "H72": (ONE_ITEM,),
    "H74": (ONE_ITEM,),
    "H77": (delivered_without_time,),
    "H80": (ONE_ITEM, in_transit_paid_by(("boleto",))),  # two orders of the customer, not tied
}
SUBSET_V1_1 = REPO_ROOT / "data" / "olist" / "subset-v1.1.json"


def draw(
    orders: dict[str, Order],
    situations: dict[str, tuple[Fits, ...]] = SITUATIONS,
    tied: dict[str, Callable[[Order, Order], bool]] = TIED,
    used: set[str] | None = None,
) -> dict[str, list[Order]]:
    """For each situation in turn, the first fitting order by the lot, never one in `used` or drawn before."""
    used = set(used or ())
    drawn: dict[str, list[Order]] = {}

    def by_lot(situation: str, found: list[Order]) -> list[Order]:
        return sorted(found, key=lambda o: hashlib.sha256(f"{situation}:{o.id}".encode()).hexdigest())

    for situation, wants in situations.items():
        tie = tied.get(situation)
        firsts = by_lot(situation, [o for o in orders.values() if o.id not in used and wants[0](o)])
        seconds = [o for o in orders.values() if o.id not in used and len(wants) > 1 and wants[1](o)]
        picked: list[Order] = []
        for first in firsts:
            if len(wants) == 1:
                picked = [first]
                break
            partners = by_lot(situation, [o for o in seconds if o.id != first.id and (tie is None or tie(first, o))])
            if partners:
                picked = [first, partners[0]]
                break
        if not picked:
            sys.exit(f"{situation}: no order, or no pair of orders, fits its shape")
        used.update(o.id for o in picked)
        print(f"{situation}: {len(firsts):6d} fit, drawn {', '.join(o.id for o in picked)}")
        drawn[situation] = picked
    return drawn


def as_record(order: Order) -> dict:
    return {
        "order_id": order.id,
        "status": order.status,
        "purchased_at": order.purchased_at,
        "delivered_at": order.delivered_at or None,
        "items": [
            {
                "order_item_id": int(i["order_item_id"]),
                "product_id": i["product_id"],
                "seller_id": i["seller_id"],
                "category": i["category"],
                "price_minor": cents(i["price"]),
                "freight_minor": cents(i["freight_value"]),
            }
            for i in order.items
        ],
        "payments": [
            {
                "sequential": int(p["payment_sequential"]),
                "method": p["payment_type"],
                "installments": int(p["payment_installments"]),
                "amount_minor": cents(p["payment_value"]),
            }
            for p in order.payments
        ],
    }


def main() -> None:
    drawn = draw(load())
    subset = {
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": "Brazilian E-Commerce Public Dataset by Olist, https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "files_sha256": FILES,
        "drawn_by": "refund_agent/olist.py",
        "situations": {situation: [as_record(o) for o in picked] for situation, picked in drawn.items()},
    }
    SUBSET.parent.mkdir(parents=True, exist_ok=True)
    SUBSET.write_text(json.dumps(subset, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {SUBSET.relative_to(REPO_ROOT)}: {sum(len(p) for p in drawn.values())} orders")


def main_v1_1() -> None:
    """The draw for the held-out set of v1.1, written to its own file: v1's subset is read, never rewritten."""
    v1 = json.loads(SUBSET.read_text(encoding="utf-8"))
    excluded = {o["order_id"] for picked in v1["situations"].values() for o in picked}
    drawn = draw(load(), SITUATIONS_V1_1, {}, used=excluded)
    subset = {
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": "Brazilian E-Commerce Public Dataset by Olist, https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "files_sha256": FILES,
        "drawn_by": "refund_agent/olist.py (main_v1_1)",
        "excluded": f"the {len(excluded)} orders of data/olist/subset.json, the held-out set of v1",
        "situations": {
            situation: [{**as_record(o), "estimated_delivery_at": o.estimated_at} for o in picked]
            for situation, picked in drawn.items()
        },
    }
    SUBSET_V1_1.write_text(json.dumps(subset, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {SUBSET_V1_1.relative_to(REPO_ROOT)}: {sum(len(p) for p in drawn.values())} orders")


if __name__ == "__main__":
    main_v1_1() if sys.argv[1:] == ["v1.1"] else main()
