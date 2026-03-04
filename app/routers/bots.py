from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import re

from app.database import get_db
from app.dependencies import require_auth, require_creation_role
from app.services.sessions import get_current_user

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
    existing = await db.bots.find_one({"slug": slug})
    if existing:
        return templates.TemplateResponse("dashboard/bot_new.html", {
            "request": request, "user": user,
            "error": f"A bot with slug '{slug}' already exists."
        })
    result = await db.bots.insert_one({
        "name": name,
        "slug": slug,
        "kb_url": kb_url,
        "scraper_settings": {
            "max_articles": scraper_max_articles,
            "depth": scraper_depth,
            "strategy": scraper_strategy,
            "delay_ms": scraper_delay_ms,
            "timeout_s": scraper_timeout_s,
            "max_chars_per_article": scraper_max_chars,
        },
        "additional_guidelines": "",
        "auto_fix_enabled": False,
        "system_prompt": "",
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return RedirectResponse(f"/dashboard/bots/{str(result.inserted_id)}/settings", status_code=302)


@router.get("/dashboard/bots/{bot_id}", response_class=HTMLResponse)
async def bot_detail(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    from bson import ObjectId
    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)
    bot["_id"] = str(bot["_id"])
    return RedirectResponse(f"/dashboard/bots/{bot_id}/settings", status_code=302)
