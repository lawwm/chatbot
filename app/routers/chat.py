import logging
import uuid
from fastapi import APIRouter, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.services.claude import chat as claude_chat, suggest_fix, merge_guidelines
from app.services.kb_scraper import get_kb_content
from app.services.kb_retrieval import retrieve_chunks
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

    # Get KB content — try vector retrieval first, fall back to full dump
    kb_urls = bot.get("kb_urls") or ([bot["kb_url"]] if bot.get("kb_url") else [])
    kb_content = await retrieve_chunks(str(bot["_id"]), message)
    if kb_content:
        logger.info("KB source=vector_search bot=%s", bot["_id"])
    else:
        logger.warning("KB source=full_dump (vector search empty) bot=%s", bot["_id"])
        kb_content = await get_kb_content(str(bot["_id"]), kb_urls, bot.get("scraper_settings"))

    # Call Claude
    assistant_text, tool_calls = await claude_chat(messages, kb_content, bot.get("additional_guidelines", ""))

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
        "tool_calls": tool_calls,
    })


async def _auto_fix_mistake(bot_id: str, mistake_id: str, bot: dict):
    """Background task: suggest fix, detect conflicts, auto-apply or queue for review."""
    logger.warning("AUTO-FIX START bot=%s mistake=%s auto_fix=%s allow_override=%s",
                   bot_id, mistake_id, bot.get("auto_fix_enabled"), bot.get("allow_override"))
    try:
        db = get_db()
        mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
        if not mistake:
            logger.warning("AUTO-FIX: mistake %s not found, aborting", mistake_id)
            return

        current_guidelines = bot.get("additional_guidelines", "")
        logger.warning("AUTO-FIX: calling suggest_fix for mistake=%s", mistake_id)
        fix = await suggest_fix(
            current_guidelines,
            mistake["customer_message"],
            mistake["bot_response"],
            mistake["complaint"],
        )
        logger.warning("AUTO-FIX: suggest_fix returned %d chars", len(fix))

        logger.warning("AUTO-FIX: calling merge_guidelines for mistake=%s", mistake_id)
        merge_result = await merge_guidelines(current_guidelines, fix)
        logger.warning("AUTO-FIX: merge_guidelines has_conflict=%s", merge_result.get("has_conflict"))

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
            logger.warning("AUTO-FIX: applied and archived mistake=%s", mistake_id)
        else:
            # Conflict + override not allowed: save for manual review
            await db.mistakes.update_one(
                {"_id": ObjectId(mistake_id)},
                {"$set": {"suggested_fix": fix, "merge_result": merge_result}},
            )
            logger.warning("AUTO-FIX: conflict detected, saved for manual review mistake=%s conflict=%s",
                           mistake_id, merge_result.get("conflict_description", ""))
    except Exception as e:
        logger.error("AUTO-FIX FAILED bot=%s mistake=%s: %s", bot_id, mistake_id, e, exc_info=True)


@router.post("/chat/{bot_slug}/report", response_class=HTMLResponse)
async def report_mistake(
    request: Request,
    background_tasks: BackgroundTasks,
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
        background_tasks.add_task(_auto_fix_mistake, str(bot["_id"]), str(result.inserted_id), bot)

    return HTMLResponse("""
        <div class="banner banner-success">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <span class="banner-msg">Thank you for your feedback. We&#39;ll review this shortly.</span>
        </div>
    """)
