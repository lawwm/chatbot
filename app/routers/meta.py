import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.dependencies import require_auth
from app.services.meta_agent import run_agent
from app.utils import render_markdown

router = APIRouter(prefix="/meta", tags=["meta"])
templates = Jinja2Templates(directory="app/templates")


async def _get_conversations(user_id: str) -> list[dict]:
    db = get_db()
    convs = await db.meta_conversations.find(
        {"user_id": user_id}
    ).sort("updated_at", -1).to_list(None)
    for c in convs:
        c.pop("_id", None)
        c.pop("messages", None)
    return convs


async def _render_page(request, user, conversations, active_conv_id, messages):
    return templates.TemplateResponse("meta/index.html", {
        "request": request,
        "user": user,
        "conversations": conversations,
        "active_conv_id": active_conv_id,
        "messages": messages,
        "render_markdown": render_markdown,
    })


@router.get("", response_class=HTMLResponse)
async def meta_index(request: Request, user: dict = Depends(require_auth)):
    user_id = str(user["_id"])
    db = get_db()
    # Clean up legacy docs without conv_id
    await db.meta_conversations.delete_many({"user_id": user_id, "conv_id": {"$exists": False}})
    latest = await db.meta_conversations.find_one(
        {"user_id": user_id}, sort=[("updated_at", -1)]
    )
    if latest:
        return RedirectResponse(f"/meta/{latest['conv_id']}", status_code=302)
    return RedirectResponse("/meta/new", status_code=302)


# NOTE: /meta/new must be declared before /meta/{conv_id} so FastAPI matches it first
@router.get("/new", response_class=HTMLResponse)
async def meta_new_page(request: Request, user: dict = Depends(require_auth)):
    """Blank chat — no conversation is created until the first message is sent."""
    user_id = str(user["_id"])
    conversations = await _get_conversations(user_id)
    return await _render_page(request, user, conversations, None, [])


@router.get("/{conv_id}", response_class=HTMLResponse)
async def meta_chat(request: Request, conv_id: str, user: dict = Depends(require_auth)):
    user_id = str(user["_id"])
    db = get_db()
    conv = await db.meta_conversations.find_one({"conv_id": conv_id, "user_id": user_id})
    if not conv:
        return RedirectResponse("/meta/new", status_code=302)
    conversations = await _get_conversations(user_id)
    return await _render_page(request, user, conversations, conv_id, conv.get("messages", []))


@router.post("/send", response_class=HTMLResponse)
async def meta_send(
    request: Request,
    message: str = Form(...),
    conv_id: str = Form(""),
    user: dict = Depends(require_auth),
):
    user_id = str(user["_id"])
    db = get_db()

    is_new = not conv_id.strip()
    if is_new:
        conv_id = uuid.uuid4().hex
        await db.meta_conversations.insert_one({
            "user_id": user_id,
            "conv_id": conv_id,
            "title": "New chat",
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

    try:
        assistant_text = await run_agent(user_id, conv_id, message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("meta_agent error: %s", e)
        assistant_text = f"Sorry, something went wrong: {e}"

    conv_title = "New chat"
    if is_new:
        conv = await db.meta_conversations.find_one({"conv_id": conv_id})
        conv_title = conv.get("title", "New chat") if conv else "New chat"

    resp = templates.TemplateResponse("meta/messages_partial.html", {
        "request": request,
        "assistant_message": assistant_text,
        "render_markdown": render_markdown,
        "is_new": is_new,
        "conv_id": conv_id,
        "conv_title": conv_title,
    })
    if is_new:
        resp.headers["HX-Push-Url"] = f"/meta/{conv_id}"
        resp.headers["HX-Trigger"] = json.dumps({"metaNewConv": {"conv_id": conv_id, "title": conv_title}})
    return resp


@router.post("/{conv_id}/rename", response_class=HTMLResponse)
async def meta_rename(
    request: Request,
    conv_id: str,
    title: str = Form(...),
    user: dict = Depends(require_auth),
):
    user_id = str(user["_id"])
    db = get_db()
    await db.meta_conversations.update_one(
        {"conv_id": conv_id, "user_id": user_id},
        {"$set": {"title": title.strip()[:80]}},
    )
    return HTMLResponse("", status_code=200)


@router.post("/{conv_id}/delete")
async def meta_delete(request: Request, conv_id: str, user: dict = Depends(require_auth)):
    user_id = str(user["_id"])
    db = get_db()
    await db.meta_conversations.delete_one({"conv_id": conv_id, "user_id": user_id})
    return RedirectResponse("/meta", status_code=302)
