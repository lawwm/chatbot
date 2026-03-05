import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SCRAPER_SETTINGS = {
    "max_articles": 30,
    "depth": 1,
    "strategy": "bfs",
    "delay_ms": 500,
    "timeout_s": 20,
    "max_chars_per_article": 2**31 - 1,
}


async def scrape_and_store(bot_id: str, kb_urls: list, scraper_settings: dict = None) -> list[dict]:
    from app.services import scrape_progress
    settings = {**DEFAULT_SCRAPER_SETTINGS, **(scraper_settings or {})}

    async def on_progress(url: str, status: str):
        await scrape_progress.push(bot_id, url, status)

    db = get_db()
    # Clear previous knowledge base before building a new one
    await db.kb_content.delete_many({"bot_id": bot_id})

    all_articles = []
    try:
        for kb_url in kb_urls:
            if not kb_url or not kb_url.strip():
                continue
            logger.info("Scraping bot=%s url=%s", bot_id, kb_url)
            try:
                articles = await _scrape(kb_url, settings, on_progress)
                all_articles.extend(articles)
            except Exception as e:
                logger.error("Scrape failed for bot=%s url=%s: %s", bot_id, kb_url, e)

        await db.kb_content.insert_one({
            "bot_id": bot_id,
            "kb_urls": kb_urls,
            "articles": all_articles,
            "scraped_at": datetime.utcnow(),
        })
        logger.info("Scrape complete for bot=%s — %d article(s) stored", bot_id, len(all_articles))
        await scrape_progress.finish(bot_id, article_count=len(all_articles))
    except Exception as e:
        logger.error("Fatal scrape error for bot=%s: %s", bot_id, e)
        await scrape_progress.finish(bot_id, article_count=0)
        raise

    # Embed and store vectors after raw articles are saved
    await _embed_and_store(bot_id, all_articles)

    return all_articles


def _chunk_text(text: str, size: int = 2000, overlap: int = 200) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


async def _embed_and_store(bot_id: str, articles: list[dict]):
    if not settings.voyage_api_key:
        logger.warning("VOYAGE_API_KEY not set — skipping embedding for bot=%s", bot_id)
        return
    if not articles:
        logger.warning("No articles to embed for bot=%s", bot_id)
        return
    try:
        import voyageai
        db = get_db()
        await db.kb_vectors.delete_many({"bot_id": bot_id})
        logger.info("Cleared existing kb_vectors for bot=%s", bot_id)

        docs = []
        texts = []
        for article in articles:
            chunks = _chunk_text(article.get("content", ""))
            for i, chunk in enumerate(chunks):
                texts.append(chunk)
                docs.append({
                    "bot_id": bot_id,
                    "article_url": article.get("url", ""),
                    "article_title": article.get("title", ""),
                    "chunk_index": i,
                    "text": chunk,
                })
        logger.info("Prepared %d chunks from %d articles for bot=%s", len(docs), len(articles), bot_id)

        logger.info("Calling Voyage AI to embed %d chunks...", len(docs))
        client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        result = await client.embed(texts, model="voyage-3-lite", input_type="document")
        logger.info("Voyage AI returned %d embeddings", len(result.embeddings))

        for doc, embedding in zip(docs, result.embeddings):
            doc["embedding"] = embedding

        insert_result = await db.kb_vectors.insert_many(docs)
        logger.info("Saved %d vectors to kb_vectors for bot=%s", len(insert_result.inserted_ids), bot_id)
    except Exception as e:
        logger.error("Embedding failed for bot=%s: %s", bot_id, e)


async def get_kb_content(bot_id: str, kb_urls: list, scraper_settings: dict = None) -> str:
    db = get_db()
    cached = await db.kb_content.find_one({"bot_id": bot_id})
    if cached:
        logger.debug("KB cache hit for bot=%s", bot_id)
        articles = cached["articles"]
    else:
        logger.info("KB cache miss for bot=%s — scraping now", bot_id)
        articles = await scrape_and_store(bot_id, kb_urls, scraper_settings)

    if not articles:
        logger.warning("No articles found for bot=%s", bot_id)
        return "No knowledge base content available."

    parts = [f"## {a['title']}\n{a['content']}" for a in articles]
    return "\n\n---\n\n".join(parts)


_CONTENT_SELECTORS = [
    "main", "article", "[role='main']",
    ".article-body", ".entry-content", ".post-content",
    ".content", ".main-content", ".page-content",
    "#content", "#main", "#main-content",
]


async def _scrape(url: str, settings: dict, on_progress=None) -> list[dict]:
    max_articles = settings["max_articles"]
    depth = settings["depth"]
    strategy = settings["strategy"]
    delay_s = settings["delay_ms"] / 1000
    timeout_ms = settings["timeout_s"] * 1000
    max_chars = settings["max_chars_per_article"]

    parsed_base = urlparse(url)
    base_netloc = parsed_base.netloc
    visited = set()
    articles = []
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
            while crawl_queue and len(articles) < max_articles:
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

                # --- Extract title ---
                title_el = soup.select_one("h1") or soup.find("title")
                title = title_el.get_text(strip=True) if title_el else current_url

                # --- Extract content (generic, priority-ordered selectors) ---
                body_el = None
                for selector in _CONTENT_SELECTORS:
                    body_el = soup.select_one(selector)
                    if body_el:
                        break
                if not body_el:
                    body_el = soup.find("body")

                content = ""
                if body_el:
                    for tag in body_el.select("nav, header, footer, script, style, noscript"):
                        tag.decompose()
                    raw = body_el.get_text(separator="\n", strip=True)
                    content = "\n".join(line for line in raw.splitlines() if line.strip())
                    content = content[:max_chars]

                if len(content) > 100:
                    articles.append({"title": title, "url": current_url, "content": content})
                    logger.debug("Scraped: %s", title)
                    if on_progress:
                        await on_progress(current_url, "scraped")
                else:
                    logger.warning("Skipped (no content): %s", current_url)
                    if on_progress:
                        await on_progress(current_url, "failed")

                # --- Follow same-domain links ---
                if current_depth < depth:
                    for a in soup.select("a[href]"):
                        href = a.get("href", "").split("#")[0].split("?")[0]
                        if not href:
                            continue
                        if href.startswith("/"):
                            href = f"{parsed_base.scheme}://{base_netloc}{href}"
                        try:
                            lp = urlparse(href)
                            if lp.netloc != base_netloc or lp.scheme not in ("http", "https"):
                                continue
                        except Exception:
                            continue
                        if href not in visited:
                            crawl_queue.append((href, current_depth + 1))

                if delay_s > 0:
                    await asyncio.sleep(delay_s)

        finally:
            await browser.close()

    logger.info("Scrape done — %d article(s) from %s", len(articles), url)
    return articles
