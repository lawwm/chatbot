import asyncio
import logging
import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.services.claude import chat as claude_chat, suggest_fix, merge_guidelines
from app.services.kb_scraper import get_kb_content
from app.services.sessions import get_current_user
from app.utils import render_markdown

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/chat/{bot_slug}", response_class=HTMLResponse)
async def chat_page(request: Request, bot_slug: str):
    db = get_db()
    bot = await db.bots.find_one({"slug": bot_slug})
    if not bot:
        return HTMLResponse("Bot not found", status_code=404)
    bot["_id"] = str(bot["_id"])

    session_id = request.cookies.get("chat_session_id") or str(uuid.uuid4())
    conversation = await db.conversations.find_one({"bot_id": bot["_id"], "session_id": session_id})
    messages = conversation["messages"] if conversation else []

    user = None
    manager_session_id = request.cookies.get("session_id")
    if manager_session_id:
        user = await get_current_user(manager_session_id)

    response = templates.TemplateResponse("chat/index.html", {
        "request": request,
        "bot": bot,
        "messages": messages,
        "session_id": session_id,
        "user": user,
        "render_markdown": render_markdown,
    })
    response.set_cookie("chat_session_id", session_id, httponly=True, samesite="lax")
    return response


@router.post("/chat/{bot_slug}/send", response_class=HTMLResponse)
async def send_message(request: Request, bot_slug: str, message: str = Form(...)):
    db = get_db()
    bot = await db.bots.find_one({"slug": bot_slug})
    if not bot:
        return HTMLResponse("Bot not found", status_code=404)
    bot["_id"] = str(bot["_id"])

    session_id = request.cookies.get("chat_session_id") or str(uuid.uuid4())

    # Load or create conversation
    conversation = await db.conversations.find_one({"bot_id": bot["_id"], "session_id": session_id})
    messages = conversation["messages"] if conversation else []

    # Add user message
    user_msg = {"role": "user", "content": message, "timestamp": datetime.utcnow()}
    messages.append(user_msg)

    # Get KB content (cached or scrape)
    kb_content = await get_kb_content(bot["_id"], bot["kb_url"], bot.get("scraper_settings"))

    # Call Claude
    assistant_text = await claude_chat(messages, kb_content, bot.get("additional_guidelines", ""))

    # Add assistant message
    assistant_msg = {"role": "assistant", "content": assistant_text, "timestamp": datetime.utcnow()}
    messages.append(assistant_msg)

    # Save conversation
    await db.conversations.update_one(
        {"bot_id": bot["_id"], "session_id": session_id},
        {"$set": {"messages": messages, "updated_at": datetime.utcnow()}},
        upsert=True,
    )

    # Return just the assistant bubble (HTMX partial)
    return templates.TemplateResponse("chat/messages_partial.html", {
        "request": request,
        "bot_id": bot["_id"],
        "session_id": session_id,
        "user_message": user_msg,
        "render_markdown": render_markdown,
        "assistant_message": assistant_msg,
    })


async def _auto_fix_mistake(bot_id: str, mistake_id: str, bot: dict):
    """Background task: suggest fix, detect conflicts, auto-apply or queue for review."""
    try:
        db = get_db()
        mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
        if not mistake:
            return

        current_guidelines = bot.get("additional_guidelines", "")
        fix = await suggest_fix(
            current_guidelines,
            mistake["customer_message"],
            mistake["bot_response"],
            mistake["complaint"],
        )
        merge_result = await merge_guidelines(current_guidelines, fix)

        allow_override = bot.get("allow_override", False)

        if not merge_result["has_conflict"] or allow_override:
            # Auto-apply: use merged (no conflict) or override_version (conflict + override allowed)
            new_guidelines = merge_result["merged"] if not merge_result["has_conflict"] else merge_result["override_version"]
            await db.bots.update_one(
                {"_id": ObjectId(bot_id)},
                {"$set": {"additional_guidelines": new_guidelines, "updated_at": datetime.utcnow()}},
            )
            await db.mistakes_archive.insert_one({
                "original_id": mistake_id,
                "bot_id": bot_id,
                "session_id": mistake.get("session_id", ""),
                "customer_message": mistake["customer_message"],
                "bot_response": mistake["bot_response"],
                "complaint": mistake["complaint"],
                "suggested_fix": fix,
                "fix_applied": new_guidelines,
                "fixed_at": datetime.utcnow(),
                "fixed_by": "auto",
                "auto_applied": True,
            })
            await db.mistakes.delete_one({"_id": ObjectId(mistake_id)})
        else:
            # Conflict + override not allowed: save for manual review
            await db.mistakes.update_one(
                {"_id": ObjectId(mistake_id)},
                {"$set": {"suggested_fix": fix, "merge_result": merge_result}},
            )
    except Exception as e:
        logger.error("Auto-fix failed for bot=%s mistake=%s: %s", bot_id, mistake_id, e)


@router.post("/chat/{bot_slug}/report", response_class=HTMLResponse)
async def report_mistake(
    request: Request,
    bot_slug: str,
    session_id: str = Form(...),
    customer_message: str = Form(...),
    bot_response: str = Form(...),
    complaint: str = Form(...),
):
    db = get_db()
    bot = await db.bots.find_one({"slug": bot_slug})
    if not bot:
        return HTMLResponse("Bot not found", status_code=404)

    result = await db.mistakes.insert_one({
        "bot_id": str(bot["_id"]),
        "session_id": session_id,
        "customer_message": customer_message,
        "bot_response": bot_response,
        "complaint": complaint,
        "status": "open",
        "suggested_fix": None,
        "created_at": datetime.utcnow(),
    })

    if bot.get("auto_fix_enabled"):
        asyncio.create_task(_auto_fix_mistake(str(bot["_id"]), str(result.inserted_id), bot))

    return HTMLResponse("""
        <div class="alert alert-success">
            Thank you for your feedback. We'll review this shortly.
        </div>
    """)
