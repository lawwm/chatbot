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


@router.get("/bots")
async def public_bot_list():
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = get_db()
    session_id = request.cookies.get("session_id")
    user = await get_current_user(session_id) if session_id else None

    if user:
        is_creator = user.get("allow_create_agent")
        user_id = str(user["_id"])
        if is_creator:
            bots = await db.bots.find().to_list(None)
        else:
            user_roles = await db.user_roles.find({"user_id": user_id}).to_list(None)
            role_bot_ids = [ObjectId(ur["bot_id"]) for ur in user_roles]
            bots = await db.bots.find({
                "$or": [
                    {"is_public": True},
                    {"_id": {"$in": role_bot_ids}},
                    {"created_by": user_id},
                ]
            }).to_list(None)
        for bot in bots:
            bot["_id"] = str(bot["_id"])
            if is_creator or bot.get("created_by") == user_id:
                bot["can_settings"] = True
            else:
                bitmap = await get_user_permission_bitmap(user_id, bot["_id"])
                bot["can_settings"] = bool(bitmap & Permission.VIEW_SETTINGS)
    else:
        bots = await db.bots.find({"is_public": True}).to_list(None)
        for bot in bots:
            bot["_id"] = str(bot["_id"])
            bot["can_settings"] = False

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
    additional_guidelines: str = Form(""),
    auto_fix_enabled: str = Form(None),
    allow_override: str = Form(None),
    is_public: str = Form(None),
    scraper_max_articles: int = Form(30),
    scraper_depth: int = Form(1),
    scraper_strategy: str = Form("bfs"),
    scraper_delay_ms: int = Form(500),
    scraper_timeout_s: int = Form(20),
    scraper_max_chars: int = Form(3000),
    user: dict = Depends(require_creation_role),
):
    db = get_db()
    form_data = await request.form()
    kb_urls = [u.strip() for u in form_data.getlist("kb_url") if u.strip()]
    if not kb_urls:
        kb_urls = ["https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card"]

    slug = slugify(name)
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
        "kb_url": kb_urls[0],
        "kb_urls": kb_urls,
        "scraper_settings": scraper_settings,
        "additional_guidelines": additional_guidelines,
        "auto_fix_enabled": auto_fix_enabled == "on",
        "allow_override": allow_override == "on",
        "is_public": is_public == "on",
        "system_prompt": "",
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    bot_id = str(result.inserted_id)

    # Create all-permissions role and assign to creator
    from app.models.role import Permission
    role_result = await db.roles.insert_one({
        "name": f"all-perms-{name}",
        "bot_id": bot_id,
        "permission_bitmap": Permission.all(),
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
    })
    await db.user_roles.insert_one({
        "user_id": str(user["_id"]),
        "role_id": str(role_result.inserted_id),
        "bot_id": bot_id,
        "granted_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
    })

    from app.services import scrape_progress
    from app.services.kb_scraper import scrape_and_store
    scrape_progress.start(bot_id)

    async def _run_scrape():
        try:
            await scrape_and_store(bot_id, kb_urls, scraper_settings)
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
    is_creator = user.get("allow_create_agent")
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
