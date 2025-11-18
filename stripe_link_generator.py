"""Generate Stripe Payment Links for products stored in Notion."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

import stripe
from notion_client import Client
from notion_client.helpers import iterate_paginated_api

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

ZERO_DECIMAL_CURRENCIES = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}


@dataclass
class Product:
    page_id: str
    name: str
    description: str
    price: float
    currency: str
    product_type: str
    payment_link: Optional[str]
    status: Optional[str]

    @property
    def needs_link(self) -> bool:
        return not self.payment_link and (self.status or "Active") == "Active"


def _require_env(value: Optional[str], key: str) -> str:
    if not value:
        raise RuntimeError(f"Environment variable {key} is required")
    return value


def _get_notion_client() -> Client:
    token = _require_env(NOTION_TOKEN, "NOTION_TOKEN")
    return Client(auth=token)


def _get_products(client: Client) -> List[Product]:
    db_id = _require_env(NOTION_DB_ID, "NOTION_DB_ID")
    results: Iterable[dict] = iterate_paginated_api(client.databases.query, **{"database_id": db_id})
    products: List[Product] = []
    for page in results:
        props = page["properties"]
        name = _extract_title(props.get("商品名"))
        if not name:
            continue
        product = Product(
            page_id=page["id"],
            name=name,
            description=_extract_rich_text(props.get("商品説明")),
            price=props.get("価格", {}).get("number") or 0,
            currency=_extract_select(props.get("通貨")) or "JPY",
            product_type=_extract_select(props.get("タイプ")) or "単発",
            payment_link=props.get("payment_link", {}).get("url"),
            status=_extract_status(props.get("ステータス")),
        )
        products.append(product)
    return products


def _extract_title(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("title", []))


def _extract_rich_text(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("rich_text", []))


def _extract_select(prop: Optional[dict]) -> Optional[str]:
    if not prop:
        return None
    option = prop.get("select")
    if isinstance(option, dict):
        return option.get("name")
    return None


def _extract_status(prop: Optional[dict]) -> Optional[str]:
    if not prop:
        return None
    status = prop.get("status")
    if isinstance(status, dict):
        return status.get("name")
    return None


def _amount_to_minor_units(amount: float, currency: str) -> int:
    currency = currency.upper()
    if currency in ZERO_DECIMAL_CURRENCIES:
        return int(round(amount))
    return int(round(amount * 100))


def _create_payment_link(product: Product) -> str:
    stripe.api_key = _require_env(STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
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


def _update_payment_link(client: Client, product: Product, link: str) -> None:
    client.pages.update(
        page_id=product.page_id,
        properties={"payment_link": {"url": link}},
    )


def main() -> None:
    client = _get_notion_client()
    products = _get_products(client)
    targets = [product for product in products if product.needs_link]
    if not targets:
        LOGGER.info("No products require a payment link.")
        return
    for product in targets:
        LOGGER.info("Creating Stripe Payment Link for %s", product.name)
        link = _create_payment_link(product)
        _update_payment_link(client, product, link)
        LOGGER.info("Updated Notion page %s", product.page_id)


if __name__ == "__main__":
    main()
