import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime

from app.database import get_db
from app.services.claude import chat as claude_chat
from app.services.kb_scraper import get_kb_content
from app.services.sessions import get_current_user

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

    # Return just the two new message bubbles (HTMX partial)
    return templates.TemplateResponse("chat/messages_partial.html", {
        "request": request,
        "bot_id": bot["_id"],
        "session_id": session_id,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
    })


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

    await db.mistakes.insert_one({
        "bot_id": str(bot["_id"]),
        "session_id": session_id,
        "customer_message": customer_message,
        "bot_response": bot_response,
        "complaint": complaint,
        "status": "open",
        "suggested_fix": None,
        "created_at": datetime.utcnow(),
    })

    return HTMLResponse("""
        <div class="alert alert-success">
            Thank you for your feedback. We'll review this shortly.
        </div>
    """)
