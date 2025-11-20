"""Generate Stripe Payment Links for products stored in Notion."""
from __future__ import annotations

import logging
import os
from typing import List

import stripe
from dotenv import load_dotenv

from notion_products import (
    ZERO_DECIMAL_CURRENCIES,
    Product,
    fetch_products,
    get_notion_client,
    require_env,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")


def _amount_to_minor_units(amount: float, currency: str) -> int:
    currency = currency.upper()
    if currency in ZERO_DECIMAL_CURRENCIES:
        return int(round(amount))
    return int(round(amount * 100))


def _create_payment_link(product: Product) -> str:
    stripe.api_key = require_env(STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    currency = product.currency.lower()
    price_data = {
        "currency": currency,
        "product_data": {
            "name": product.name,
            "description": product.description[:500],
        },
        "unit_amount": _amount_to_minor_units(product.price, product.currency),
    }
    if product.product_type == "サブスク":
        price_data["recurring"] = {"interval": "month"}
    payment_link = stripe.PaymentLink.create(
        line_items=[{"price_data": price_data, "quantity": 1}],
        metadata={"notion_page_id": product.page_id},
    )
    return payment_link.get("url")


def _update_payment_link(product: Product, link: str) -> None:
    client = get_notion_client()
    client.pages.update(
        page_id=product.page_id,
        properties={"payment_link": {"url": link}},
    )


def main() -> None:
    products: List[Product] = fetch_products()
    targets = [product for product in products if product.needs_link]
    if not targets:
        LOGGER.info("No products require a payment link.")
        return
    for product in targets:
        LOGGER.info("Creating Stripe Payment Link for %s", product.name)
        link = _create_payment_link(product)
        _update_payment_link(product, link)
        LOGGER.info("Updated Notion page %s", product.page_id)


if __name__ == "__main__":
    main()
