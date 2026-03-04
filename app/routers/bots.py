from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import re
import uuid

import asyncio
from bson import ObjectId
from app.database import get_db
from app.dependencies import require_auth, require_creation_role
from app.services.sessions import get_current_user
from app.services.permissions import get_user_permission_bitmap
from app.models.role import Permission

router = APIRouter(tags=["bots"])
templates = Jinja2Templates(directory="app/templates")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("/bots", response_class=HTMLResponse)
async def public_bot_list(request: Request):
    db = get_db()
    user = None
    session_id = request.cookies.get("session_id")
    if session_id:
        user = await get_current_user(session_id)
    bots = await db.bots.find().to_list(None)
    for bot in bots:
        bot["_id"] = str(bot["_id"])
    return templates.TemplateResponse("bots/index.html", {
        "request": request, "user": user, "bots": bots
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(require_auth)):
    db = get_db()
    if user.get("has_creation_role"):
        bots = await db.bots.find().to_list(None)
    else:
        user_roles = await db.user_roles.find({"user_id": str(user["_id"])}).to_list(None)
        bot_ids = list({ur["bot_id"] for ur in user_roles})
        bots = await db.bots.find({"_id": {"$in": bot_ids}}).to_list(None)
    for bot in bots:
        bot["_id"] = str(bot["_id"])
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request, "user": user, "bots": bots
    })


@router.get("/dashboard/bots/new", response_class=HTMLResponse)
async def new_bot_page(request: Request, user: dict = Depends(require_creation_role)):
    return templates.TemplateResponse("dashboard/bot_new.html", {"request": request, "user": user})


@router.post("/dashboard/bots/new")
async def create_bot(
    request: Request,
    name: str = Form(...),
    kb_url: str = Form("https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card"),
    additional_guidelines: str = Form(""),
    auto_fix_enabled: str = Form(None),
    scraper_max_articles: int = Form(30),
    scraper_depth: int = Form(1),
    scraper_strategy: str = Form("bfs"),
    scraper_delay_ms: int = Form(500),
    scraper_timeout_s: int = Form(20),
    scraper_max_chars: int = Form(3000),
    user: dict = Depends(require_creation_role),
):
    db = get_db()
    slug = slugify(name)
    # ensure slug uniqueness by appending random suffix if needed
    base_slug = slug
    counter = 1
    while await db.bots.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    scraper_settings = {
        "max_articles": scraper_max_articles,
        "depth": scraper_depth,
        "strategy": scraper_strategy,
        "delay_ms": scraper_delay_ms,
        "timeout_s": scraper_timeout_s,
        "max_chars_per_article": scraper_max_chars,
    }
    result = await db.bots.insert_one({
        "name": name,
        "slug": slug,
        "bot_uuid": uuid.uuid4().hex[:9],
        "kb_url": kb_url,
        "scraper_settings": scraper_settings,
        "additional_guidelines": additional_guidelines,
        "auto_fix_enabled": auto_fix_enabled == "on",
        "system_prompt": "",
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    bot_id = str(result.inserted_id)

    from app.services import scrape_progress
    from app.services.kb_scraper import scrape_and_store
    scrape_progress.start(bot_id)

    async def _run_scrape():
        try:
            await scrape_and_store(bot_id, kb_url, scraper_settings)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Scrape failed on creation for bot=%s: %s", bot_id, e)
            await scrape_progress.finish(bot_id, article_count=0)

    asyncio.create_task(_run_scrape())
    return RedirectResponse(f"/dashboard/bots/{bot_id}/settings?scraping=1", status_code=302)


@router.post("/dashboard/bots/{bot_id}/delete")
async def delete_bot(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    user_id = str(user["_id"])
    is_creator = user.get("has_creation_role")
    is_bot_creator = bot.get("created_by") == user_id
    bitmap = await get_user_permission_bitmap(user_id, bot_id)
    can_delete = is_creator or is_bot_creator or bool(bitmap & Permission.DELETE_BOT)

    if not can_delete:
        return RedirectResponse(f"/dashboard/bots/{bot_id}/settings", status_code=302)

    await db.bots.delete_one({"_id": ObjectId(bot_id)})
    await db.roles.delete_many({"bot_id": bot_id})
    await db.user_roles.delete_many({"bot_id": bot_id})
    await db.kb_content.delete_many({"bot_id": bot_id})
    await db.mistakes.delete_many({"bot_id": bot_id})
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/dashboard/bots/{bot_id}", response_class=HTMLResponse)
async def bot_detail(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    from bson import ObjectId
    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)
    bot["_id"] = str(bot["_id"])
    return RedirectResponse(f"/dashboard/bots/{bot_id}/settings", status_code=302)
