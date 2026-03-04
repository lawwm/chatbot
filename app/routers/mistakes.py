from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.dependencies import require_auth
from app.services.permissions import get_user_permission_bitmap, has_creation_role
from app.services.claude import suggest_fix
from app.models.role import Permission

router = APIRouter(tags=["mistakes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard/bots/{bot_id}/mistakes", response_class=HTMLResponse)
async def mistakes_page(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    bitmap = await get_user_permission_bitmap(str(user["_id"]), bot_id)
    is_creator = await has_creation_role(user)
    if not is_creator and not (bitmap & Permission.REVIEW_MISTAKES):
        return HTMLResponse("Access denied", status_code=403)

    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return HTMLResponse("Bot not found", status_code=404)
    bot["_id"] = str(bot["_id"])

    open_mistakes = await db.mistakes.find(
        {"bot_id": bot_id, "status": "open"}
    ).sort("created_at", -1).to_list(None)
    for m in open_mistakes:
        m["_id"] = str(m["_id"])

    archived = await db.mistakes_archive.find(
        {"bot_id": bot_id}
    ).sort("fixed_at", -1).limit(20).to_list(None)
    for m in archived:
        m["_id"] = str(m["_id"])

    can_approve = is_creator or bool(bitmap & Permission.APPROVE_FIXES)

    return templates.TemplateResponse("dashboard/mistakes.html", {
        "request": request, "user": user, "bot": bot,
        "open_mistakes": open_mistakes, "archived": archived,
        "can_approve": can_approve,
    })


@router.post("/dashboard/bots/{bot_id}/mistakes/{mistake_id}/analyze", response_class=HTMLResponse)
async def analyze_mistake(
    request: Request,
    bot_id: str,
    mistake_id: str,
    user: dict = Depends(require_auth),
):
    db = get_db()
    mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
    if not mistake:
        return HTMLResponse("Mistake not found", status_code=404)

    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    current_guidelines = bot.get("additional_guidelines", "") if bot else ""

    fix = await suggest_fix(
        current_guidelines,
        mistake["customer_message"],
        mistake["bot_response"],
        mistake["complaint"],
    )

    await db.mistakes.update_one(
        {"_id": ObjectId(mistake_id)},
        {"$set": {"suggested_fix": fix}},
    )

    return templates.TemplateResponse("dashboard/mistake_fix_partial.html", {
        "request": request,
        "bot_id": bot_id,
        "mistake_id": mistake_id,
        "suggested_fix": fix,
    })


@router.post("/dashboard/bots/{bot_id}/mistakes/{mistake_id}/apply", response_class=HTMLResponse)
async def apply_fix(
    request: Request,
    bot_id: str,
    mistake_id: str,
    fix: str = Form(...),
    user: dict = Depends(require_auth),
):
    db = get_db()
    bitmap = await get_user_permission_bitmap(str(user["_id"]), bot_id)
    is_creator = await has_creation_role(user)
    if not is_creator and not (bitmap & Permission.APPROVE_FIXES):
        return HTMLResponse("Access denied", status_code=403)

    mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
    if not mistake:
        return HTMLResponse("Mistake not found", status_code=404)

    # Apply the fix to bot guidelines
    await db.bots.update_one(
        {"_id": ObjectId(bot_id)},
        {"$set": {"additional_guidelines": fix, "updated_at": datetime.utcnow()}},
    )

    # Archive the mistake
    await db.mistakes_archive.insert_one({
        "original_id": mistake_id,
        "bot_id": bot_id,
        "session_id": mistake["session_id"],
        "customer_message": mistake["customer_message"],
        "bot_response": mistake["bot_response"],
        "complaint": mistake["complaint"],
        "suggested_fix": mistake.get("suggested_fix", ""),
        "fix_applied": fix,
        "fixed_at": datetime.utcnow(),
        "fixed_by": str(user["_id"]),
    })

    # Remove from open mistakes
    await db.mistakes.delete_one({"_id": ObjectId(mistake_id)})

    return HTMLResponse(f"""
        <div class="alert alert-success">
            Fix applied and mistake archived. Guidelines updated.
            <script>setTimeout(() => window.location.reload(), 1500);</script>
        </div>
    """)
