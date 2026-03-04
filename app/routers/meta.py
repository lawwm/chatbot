from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId
import re

from app.database import get_db
from app.dependencies import require_creation_role
from app.services.claude import generate_bot_config

router = APIRouter(prefix="/meta", tags=["meta"])
templates = Jinja2Templates(directory="app/templates")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("", response_class=HTMLResponse)
async def meta_page(request: Request, user: dict = Depends(require_creation_role)):
    db = get_db()
    bots = await db.bots.find({"created_by": str(user["_id"])}).to_list(None)
    for b in bots:
        b["_id"] = str(b["_id"])
    return templates.TemplateResponse("meta/index.html", {
        "request": request, "user": user, "bots": bots
    })


@router.post("/generate", response_class=HTMLResponse)
async def generate_agent(
    request: Request,
    bot_name: str = Form(...),
    manager_instructions: str = Form(...),
    doc_file: UploadFile = File(None),
    user: dict = Depends(require_creation_role),
):
    doc_content = ""
    if doc_file and doc_file.filename:
        raw = await doc_file.read()
        try:
            doc_content = raw.decode("utf-8")
        except UnicodeDecodeError:
            doc_content = raw.decode("latin-1", errors="ignore")

    config = await generate_bot_config(doc_content, manager_instructions)

    db = get_db()
    slug = slugify(bot_name)
    existing = await db.bots.find_one({"slug": slug})
    suffix = 1
    original_slug = slug
    while existing:
        slug = f"{original_slug}-{suffix}"
        suffix += 1
        existing = await db.bots.find_one({"slug": slug})

    result = await db.bots.insert_one({
        "name": bot_name,
        "slug": slug,
        "kb_url": config.get("kb_url", ""),
        "additional_guidelines": config.get("additional_guidelines", ""),
        "auto_fix_enabled": False,
        "system_prompt": "",
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    bot_id = str(result.inserted_id)

    return templates.TemplateResponse("meta/result_partial.html", {
        "request": request,
        "bot_id": bot_id,
        "bot_name": bot_name,
        "bot_slug": slug,
        "config": config,
    })
