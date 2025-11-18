"""Generate static landing pages from Notion product data."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from slugify import slugify

OUTPUT_DIR = Path("pages")
TEMPLATE_DIR = Path("templates")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

CTA_LABELS = {"単発": "今すぐ購入", "サブスク": "定期購入を開始"}
CURRENCY_SYMBOLS = {"JPY": "¥", "USD": "$"}
ZERO_DECIMAL_CURRENCIES = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}


def _require_env(value: Optional[str], key: str) -> str:
    if not value:
        raise RuntimeError(f"Environment variable {key} is required")
    return value


def _get_notion_client() -> Client:
    token = _require_env(NOTION_TOKEN, "NOTION_TOKEN")
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
    def is_publishable(self) -> bool:
        return (self.status or "Active") == "Active" and bool(self.payment_link)

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


def _render_template(product: Product) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("lp_template.html")
    return template.render(product={
        "name": product.name,
        "description": product.description or "",
        "payment_link": product.payment_link,
        "price_label": product.price_label,
        "cta_label": product.cta_label,
    })


def _write_page(product: Product, html: str) -> Path:
    target_dir = OUTPUT_DIR / product.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    client = _get_notion_client()
    products = [product for product in _get_products(client) if product.is_publishable]
    if not products:
        print("No products to publish")
        return
    OUTPUT_DIR.mkdir(exist_ok=True)
    manifest = []
    for product in products:
        html = _render_template(product)
        path = _write_page(product, html)
        manifest.append({"name": product.name, "slug": product.slug, "path": str(path)})
        print(f"Generated {path}")
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
