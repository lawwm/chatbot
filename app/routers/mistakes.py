import asyncio
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.dependencies import require_auth
from app.services.permissions import get_user_permission_bitmap, has_creation_role
from app.services.claude import suggest_fix, merge_guidelines
from app.models.role import Permission
from app.utils import render_markdown

router = APIRouter(tags=["mistakes"])
templates = Jinja2Templates(directory="app/templates")


async def _archive_mistake(db, bot_id: str, mistake_id: str, new_guidelines: str,
                            fix: str, fixed_by: str, auto_applied: bool = False):
    """Apply guidelines update and move mistake to archive."""
    mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
    if not mistake:
        return None
    await db.bots.update_one(
        {"_id": ObjectId(bot_id)},
        {"$set": {"additional_guidelines": new_guidelines, "updated_at": datetime.utcnow()}},
    )
    doc = {
        "original_id": mistake_id,
        "bot_id": bot_id,
        "session_id": mistake.get("session_id", ""),
        "customer_message": mistake["customer_message"],
        "bot_response": mistake["bot_response"],
        "complaint": mistake["complaint"],
        "suggested_fix": mistake.get("suggested_fix", fix),
        "fix_applied": new_guidelines,
        "fixed_at": datetime.utcnow(),
        "fixed_by": fixed_by,
        "auto_applied": auto_applied,
    }
    result = await db.mistakes_archive.insert_one(doc)
    await db.mistakes.delete_one({"_id": ObjectId(mistake_id)})
    doc["_id"] = str(result.inserted_id)
    doc["fixed_at_display"] = doc["fixed_at"].strftime("%Y-%m-%d %H:%M")
    return doc


def _archive_row_html(doc: dict) -> str:
    cm = doc.get("customer_message", "")[:80]
    complaint = doc.get("complaint", "")[:80]
    fix = doc.get("fix_applied", "")[:100]
    fixed_at = doc.get("fixed_at_display", "")
    return (
        f'<tr hx-swap-oob="afterbegin:#archive-tbody">'
        f'<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{cm}</td>'
        f'<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{complaint}</td>'
        f'<td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{fix}</td>'
        f'<td style="white-space:nowrap;">{fixed_at}</td>'
        f'</tr>'
    )


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
        {"bot_id": bot_id, "status": {"$ne": "archived"}}
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
        "render_markdown": render_markdown,
    })


@router.get("/dashboard/bots/{bot_id}/mistakes/archive-partial", response_class=HTMLResponse)
async def archive_partial(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    archived = await db.mistakes_archive.find(
        {"bot_id": bot_id}
    ).sort("fixed_at", -1).limit(20).to_list(None)
    for m in archived:
        m["_id"] = str(m["_id"])
    return templates.TemplateResponse("dashboard/mistakes_archive_partial.html", {
        "request": request, "archived": archived,
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

    merge_result = await merge_guidelines(current_guidelines, fix)

    await db.mistakes.update_one(
        {"_id": ObjectId(mistake_id)},
        {"$set": {
            "suggested_fix": fix,
            "merge_result": merge_result,
        }},
    )

    if merge_result["has_conflict"]:
        return templates.TemplateResponse("dashboard/mistake_conflict_partial.html", {
            "request": request,
            "bot_id": bot_id,
            "mistake_id": mistake_id,
            "conflict_description": merge_result["conflict_description"],
            "override_version": merge_result["override_version"],
            "keep_version": merge_result["keep_version"],
        })

    return templates.TemplateResponse("dashboard/mistake_fix_partial.html", {
        "request": request,
        "bot_id": bot_id,
        "mistake_id": mistake_id,
        "suggested_fix": merge_result["merged"],
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

    doc = await _archive_mistake(db, bot_id, mistake_id, fix, fix, str(user["_id"]))
    if not doc:
        return HTMLResponse("Mistake not found", status_code=404)

    response = HTMLResponse(content=f'<div id="mistake-{mistake_id}" style="display:none"></div>')
    response.headers["HX-Trigger"] = "mistakeArchived"
    return response
