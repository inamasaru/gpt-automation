# gpt-automation

This repository automates an entire sales funnel from a single Notion database:

1. **Stripe Payment Link generation** – `stripe_link_generator.py` looks for products in the Product Master DB that do not yet have a `payment_link` and creates one through the Stripe API.
2. **Landing page auto-generation** – `lp_autogen.py` renders static LPs from a shared HTML template and the Notion product data.
3. **Cloudflare Pages deployment** – Generated LPs are deployed through GitHub Actions and Cloudflare Pages.
4. **Scheduled GitHub Actions** – Two workflows keep Stripe links and LPs fresh every day.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Required environment variables

Both scripts rely on the following environment variables (`python-dotenv` is loaded automatically if you create a `.env` file locally):

| Variable | Description |
| --- | --- |
| `NOTION_TOKEN` | Internal integration token with access to the Product Master DB |
| `NOTION_DB_ID` | Database ID of the Product Master DB |
| `STRIPE_SECRET_KEY` | (Stripe link generation only) secret API key used to create Payment Links |

### Keepa Slack notifier

`profit_bot.py` can be run on its own or via the provided GitHub Actions workflows to verify Keepa + Slack connectivity.

| Variable | Description |
| --- | --- |
| `KEEPA_API_KEY` | Keepa API key |
| `SLACK_WEBHOOK_URL` | Incoming webhook for the Slack channel that should receive alerts |
| `KEEPA_DOMAIN` | (Optional) Keepa domain ID. Defaults to `6` (JP). |
| `KEEPA_TEST_ASIN` | (Optional) ASIN to probe when validating the integration. Defaults to `B08N5WRNW`. |

Manual run:

```bash
python profit_bot.py
```

To run the scripts manually:

```bash
python stripe_link_generator.py
python lp_autogen.py
```

## GitHub Actions

| Workflow | Path | Description | Secrets |
| --- | --- | --- | --- |
| Stripe Payment Links | `.github/workflows/stripe_links.yml` | Runs daily via cron to fill missing `payment_link` fields in Notion. | `NOTION_TOKEN`, `NOTION_DB_ID`, `STRIPE_SECRET_KEY` |
| LP Auto Deploy | `.github/workflows/lp_autogen.yml` | Runs after the Stripe workflow succeeds (or manually) to rebuild LPs and deploy to Cloudflare Pages. | `NOTION_TOKEN`, `NOTION_DB_ID`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PROJECT_NAME` |

> The LP workflow uploads the freshly generated `pages/` directory as an artifact and deploys it through `cloudflare/pages-action@v1`.

## Cloudflare deployment flow

1. `lp_autogen.py` reads all active products that already have a Stripe Payment Link and renders `pages/<slug>/index.html` using `templates/lp_template.html`.
2. `pages/manifest.json` is written so you can track which slugs were published.
3. The GitHub Action uploads `pages/` and triggers a Cloudflare Pages deployment with the provided credentials.

## Steps to get everything running

1. **Create a Notion integration** with read/write access to the Product Master database and copy the token + database ID.
2. **Prepare Stripe** – ensure your account has the products enabled you want to sell and copy the secret API key.
3. **Configure GitHub Secrets** under *Settings → Secrets and variables → Actions*:
   - `NOTION_TOKEN`
   - `NOTION_DB_ID`
   - `STRIPE_SECRET_KEY`
   - `CLOUDFLARE_API_TOKEN` (Pages `Edit` + `Deployments` permissions)
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_PROJECT_NAME`
4. (Optional) **Create a `.env`** locally with the same keys for manual execution.
5. **Push to GitHub** – once secrets are configured, the scheduled workflows will start running automatically. You can also trigger them manually from the Actions tab if you need immediate regeneration.
