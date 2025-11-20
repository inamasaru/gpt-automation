"""Shared helpers for fetching product data from Notion."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from dotenv import load_dotenv
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from slugify import slugify

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

CTA_LABELS = {"単発": "今すぐ購入", "サブスク": "定期購入を開始"}
CURRENCY_SYMBOLS = {"JPY": "¥", "USD": "$"}
ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "JPY",
    "KMF",
    "KRW",
    "MGA",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}


def require_env(value: Optional[str], key: str) -> str:
    if not value:
        raise RuntimeError(f"Environment variable {key} is required")
    return value


def get_notion_client() -> Client:
    token = require_env(NOTION_TOKEN, "NOTION_TOKEN")
    return Client(auth=token)


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
    def is_active(self) -> bool:
        return (self.status or "Active") == "Active"

    @property
    def is_publishable(self) -> bool:
        return self.is_active and bool(self.payment_link)

    @property
    def needs_link(self) -> bool:
        return self.is_active and not self.payment_link

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def price_label(self) -> str:
        symbol = CURRENCY_SYMBOLS.get(self.currency.upper(), self.currency.upper())
        if self.currency.upper() in ZERO_DECIMAL_CURRENCIES:
            amount = f"{int(round(self.price)):,}"
        else:
            amount = f"{self.price:,.2f}"
        return f"{symbol}{amount}" if symbol else amount

    @property
    def cta_label(self) -> str:
        return CTA_LABELS.get(self.product_type, "お申し込みはこちら")


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


def _build_product(page: dict) -> Product:
    props = page["properties"]
    name = _extract_title(props.get("商品名"))
    return Product(
        page_id=page["id"],
        name=name,
        description=_extract_rich_text(props.get("商品説明")),
        price=props.get("価格", {}).get("number") or 0,
        currency=_extract_select(props.get("通貨")) or "JPY",
        product_type=_extract_select(props.get("タイプ")) or "単発",
        payment_link=props.get("payment_link", {}).get("url"),
        status=_extract_status(props.get("ステータス")),
    )


def fetch_products(client: Optional[Client] = None) -> List[Product]:
    notion = client or get_notion_client()
    db_id = require_env(NOTION_DB_ID, "NOTION_DB_ID")
    results: Iterable[dict] = iterate_paginated_api(
        notion.databases.query, **{"database_id": db_id}
    )
    products: List[Product] = []
    for page in results:
        name = _extract_title(page.get("properties", {}).get("商品名"))
        if not name:
            continue
        products.append(_build_product(page))
    return products
