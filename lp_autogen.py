"""Generate static landing pages from Notion product data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from notion_products import Product, fetch_products

load_dotenv()

OUTPUT_DIR = Path("pages")
TEMPLATE_DIR = Path("templates")


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
    products: List[Product] = [product for product in fetch_products() if product.is_publishable]
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
