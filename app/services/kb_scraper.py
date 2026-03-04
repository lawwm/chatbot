import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from app.database import get_db

logger = logging.getLogger(__name__)

DEFAULT_SCRAPER_SETTINGS = {
    "max_articles": 30,
    "depth": 1,
    "strategy": "bfs",
    "delay_ms": 500,
    "timeout_s": 20,
    "max_chars_per_article": 3000,
}


async def scrape_and_store(bot_id: str, kb_url: str, scraper_settings: dict = None) -> list[dict]:
    from app.services import scrape_progress
    settings = {**DEFAULT_SCRAPER_SETTINGS, **(scraper_settings or {})}
    logger.info("Starting scrape for bot=%s url=%s settings=%s", bot_id, kb_url, settings)

    async def on_progress(url: str, status: str):
        await scrape_progress.push(bot_id, url, status)

    try:
        articles = await _scrape(kb_url, settings, on_progress)
    except Exception as e:
        await scrape_progress.finish(bot_id, article_count=0)
        raise

    # get db
    db = get_db()
    await db.kb_content.replace_one(
        {"bot_id": bot_id},
        {"bot_id": bot_id, "kb_url": kb_url, "articles": articles, "scraped_at": datetime.utcnow()},
        upsert=True,
    )
    logger.info("Scrape complete for bot=%s — %d article(s) stored", bot_id, len(articles))
    await scrape_progress.finish(bot_id, article_count=len(articles))
    return articles


async def get_kb_content(bot_id: str, kb_url: str, scraper_settings: dict = None) -> str:
    db = get_db()
    cached = await db.kb_content.find_one({"bot_id": bot_id, "kb_url": kb_url})
    if cached:
        logger.debug("KB cache hit for bot=%s", bot_id)
        articles = cached["articles"]
    else:
        logger.info("KB cache miss for bot=%s — scraping now", bot_id)
        articles = await scrape_and_store(bot_id, kb_url, scraper_settings)

    if not articles:
        logger.warning("No articles found for bot=%s url=%s", bot_id, kb_url)
        return "No knowledge base content available."

    parts = [f"## {a['title']}\n{a['content']}" for a in articles]
    return "\n\n---\n\n".join(parts)


async def _scrape(url: str, settings: dict, on_progress=None) -> list[dict]:
    max_articles = settings["max_articles"]
    depth = settings["depth"]
    strategy = settings["strategy"]
    delay_s = settings["delay_ms"] / 1000
    timeout_ms = settings["timeout_s"] * 1000
    max_chars = settings["max_chars_per_article"]

    parsed_base = urlparse(url)
    visited = set()
    article_links = []
    crawl_queue = [(url, 0)]
    use_bfs = strategy == "bfs"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))

        try:
            # Phase 1: collect article links
            while crawl_queue and len(article_links) < max_articles:
                current_url, current_depth = crawl_queue.pop(0) if use_bfs else crawl_queue.pop()
                if current_url in visited:
                    continue
                visited.add(current_url)

                logger.debug("Fetching (depth=%d): %s", current_depth, current_url)
                if on_progress:
                    await on_progress(current_url, "visiting")

                try:
                    await page.goto(current_url, timeout=timeout_ms, wait_until="domcontentloaded")
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", current_url, e)
                    if on_progress:
                        await on_progress(current_url, "failed")
                    continue

                soup = BeautifulSoup(await page.content(), "html.parser")

                for a in soup.select("a[href]"):
                    href = a["href"]
                    if href.startswith("/"):
                        href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    if "/hc/en-gb/articles/" in href and href not in article_links:
                        article_links.append(href)
                        if len(article_links) >= max_articles:
                            break

                if current_depth < depth:
                    for a in soup.select("a[href]"):
                        href = a["href"]
                        if href.startswith("/"):
                            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                        if (
                            parsed_base.netloc in href
                            and "/hc/en-gb/" in href
                            and "/articles/" not in href
                            and href not in visited
                        ):
                            crawl_queue.append((href, current_depth + 1))

                if delay_s > 0:
                    await asyncio.sleep(delay_s)

            logger.info("Found %d article link(s) from %s", len(article_links), url)

            # Phase 2: scrape articles
            articles = []
            for link in article_links:
                if delay_s > 0:
                    await asyncio.sleep(delay_s)
                try:
                    await page.goto(link, timeout=timeout_ms, wait_until="domcontentloaded")
                    soup = BeautifulSoup(await page.content(), "html.parser")
                    title_el = soup.select_one("h1.article-title, h1")
                    body_el = soup.select_one(".article-body, article")
                    if title_el and body_el:
                        articles.append({
                            "title": title_el.get_text(strip=True),
                            "url": link,
                            "content": body_el.get_text(separator="\n", strip=True)[:max_chars],
                        })
                        logger.debug("Scraped: %s", title_el.get_text(strip=True))
                        if on_progress:
                            await on_progress(link, "scraped")
                    else:
                        logger.warning("Skipped (missing title/body): %s", link)
                        if on_progress:
                            await on_progress(link, "failed")
                except Exception as e:
                    logger.warning("Failed to scrape %s: %s", link, e)
                    if on_progress:
                        await on_progress(link, "failed")
        finally:
            await browser.close()

    return articles
