import asyncio
import logging
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.dependencies import require_auth
from app.services.permissions import get_user_permission_bitmap, has_creation_role
from app.services.kb_scraper import scrape_and_store
from app.services import scrape_progress
from app.models.role import Permission

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


async def get_bot_or_404(bot_id: str):
    db = get_db()
    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return None
    bot["_id"] = str(bot["_id"])
    return bot


@router.get("/dashboard/bots/{bot_id}/settings", response_class=HTMLResponse)
async def settings_page(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    bot = await get_bot_or_404(bot_id)
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)
    user_id = str(user["_id"])
    bitmap = await get_user_permission_bitmap(user_id, bot_id)
    is_creator = await has_creation_role(user)
    permissions = {
        "edit_kb_url": is_creator or bool(bitmap & Permission.EDIT_KB_URL),
        "edit_guidelines": is_creator or bool(bitmap & Permission.EDIT_GUIDELINES),
        "toggle_autofix": is_creator or bool(bitmap & Permission.TOGGLE_AUTOFIX),
        "review_mistakes": is_creator or bool(bitmap & Permission.REVIEW_MISTAKES),
        "manage_roles": is_creator or bool(bitmap & Permission.MANAGE_ROLES),
    }
    db = get_db()
    kb = await db.kb_content.find_one({"bot_id": bot_id})
    kb_stats = None
    if kb:
        kb_stats = {
            "article_count": len(kb.get("articles", [])),
            "scraped_at": kb.get("scraped_at"),
        }
    return templates.TemplateResponse("dashboard/bot_settings.html", {
        "request": request, "user": user, "bot": bot, "permissions": permissions,
        "scraping": scrape_progress.is_active(bot_id),
        "kb_stats": kb_stats,
    })


@router.post("/dashboard/bots/{bot_id}/settings")
async def update_settings(
    request: Request,
    bot_id: str,
    kb_url: str = Form(None),
    additional_guidelines: str = Form(None),
    auto_fix_enabled: str = Form(None),
    user: dict = Depends(require_auth),
):
    db = get_db()
    user_id = str(user["_id"])
    bitmap = await get_user_permission_bitmap(user_id, bot_id)
    is_creator = await has_creation_role(user)

    updates = {"updated_at": datetime.utcnow()}
    trigger_scrape = False

    if kb_url is not None and (is_creator or bitmap & Permission.EDIT_KB_URL):
        updates["kb_url"] = kb_url
        trigger_scrape = True

    if additional_guidelines is not None and (is_creator or bitmap & Permission.EDIT_GUIDELINES):
        updates["additional_guidelines"] = additional_guidelines

    if is_creator or bitmap & Permission.TOGGLE_AUTOFIX:
        updates["auto_fix_enabled"] = auto_fix_enabled == "on"

    await db.bots.update_one({"_id": ObjectId(bot_id)}, {"$set": updates})

    if trigger_scrape:
        bot = await get_bot_or_404(bot_id)
        scraper_settings = bot.get("scraper_settings")
        scrape_progress.start(bot_id)

        async def _run_scrape():
            try:
                await scrape_and_store(bot_id, kb_url, scraper_settings)
            except Exception as e:
                logger.error("Background scrape failed for bot=%s: %s", bot_id, e)
                await scrape_progress.finish(bot_id, article_count=0)

        asyncio.create_task(_run_scrape())
        return RedirectResponse(f"/dashboard/bots/{bot_id}/settings?scraping=1", status_code=302)

    return RedirectResponse(f"/dashboard/bots/{bot_id}/settings?saved=1", status_code=302)


@router.get("/dashboard/bots/{bot_id}/scrape-stream")
async def scrape_stream(bot_id: str, user: dict = Depends(require_auth)):
    async def generate():
        try:
            while True:
                event = await scrape_progress.get_event(bot_id, timeout=120)
                if event is None or event.get("timeout"):
                    yield "data: __done__\n\n"
                    break
                if event.get("done"):
                    count = event.get("article_count", 0)
                    yield f"data: __done__{count}\n\n"
                    break
                status = event["status"]
                url = event["url"]
                yield f"data: {status}|{url}\n\n"
        finally:
            scrape_progress.cleanup(bot_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
