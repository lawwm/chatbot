"""Standalone async test for the Playwright scraper. Run from project root."""
import asyncio
import sys
import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s — %(message)s")

sys.path.insert(0, ".")
from app.services.kb_scraper import _scrape, DEFAULT_SCRAPER_SETTINGS

url = "https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card"
settings = {**DEFAULT_SCRAPER_SETTINGS, "max_articles": 5}


async def main():
    print(f"\nScraping: {url}\n")

    async def on_progress(u, status):
        icon = {"visiting": "→", "scraped": "✓", "failed": "✗"}.get(status, "·")
        print(f"  {icon} [{status}] {u}")

    try:
        articles = await _scrape(url, settings, on_progress)
    except Exception as e:
        import traceback
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\nDone — {len(articles)} article(s):")
    for a in articles:
        print(f"  - {a['title']}")


asyncio.run(main())
