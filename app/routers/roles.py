from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId

from app.database import get_db
from app.dependencies import require_creation_role, require_auth
from app.services.permissions import get_user_permission_bitmap
from app.models.role import Permission

router = APIRouter(prefix="/dashboard/bots/{bot_id}/roles", tags=["roles"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["bitwise_and"] = lambda a, b: int(a) & int(b)


@router.get("", response_class=HTMLResponse)
async def roles_page(request: Request, bot_id: str, user: dict = Depends(require_auth)):
    db = get_db()
    bitmap = await get_user_permission_bitmap(str(user["_id"]), bot_id)
    is_creator = user.get("allow_create_agent")
    if not is_creator and not (bitmap & Permission.MANAGE_ROLES):
        return RedirectResponse(f"/dashboard/bots/{bot_id}/settings", status_code=302)

    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)
    bot["_id"] = str(bot["_id"])

    roles = await db.roles.find({"bot_id": bot_id}).to_list(None)
    for r in roles:
        r["_id"] = str(r["_id"])

    users = await db.users.find().to_list(None)
    for u in users:
        u["_id"] = str(u["_id"])

    user_roles = await db.user_roles.find({"bot_id": bot_id}).to_list(None)
    for ur in user_roles:
        ur["_id"] = str(ur["_id"])

    all_permissions = [(p.value, p.name.replace("_", " ").title()) for p in Permission]

    return templates.TemplateResponse("dashboard/roles.html", {
        "request": request, "user": user, "bot": bot,
        "roles": roles, "users": users, "user_roles": user_roles,
        "all_permissions": all_permissions,
    })


@router.post("/create")
async def create_role(
    request: Request,
    bot_id: str,
    name: str = Form(...),
    permission_bitmap: int = Form(0),
    user: dict = Depends(require_auth),
):
    db = get_db()
    await db.roles.insert_one({
        "name": name,
        "bot_id": bot_id,
        "permission_bitmap": permission_bitmap,
        "created_by": str(user["_id"]),
        "created_at": datetime.utcnow(),
    })
    return RedirectResponse(f"/dashboard/bots/{bot_id}/roles", status_code=302)


@router.post("/assign")
async def assign_role(
    request: Request,
    bot_id: str,
    user_id: str = Form(...),
    role_id: str = Form(...),
    granting_user: dict = Depends(require_auth),
):
    db = get_db()
    existing = await db.user_roles.find_one({"user_id": user_id, "role_id": role_id, "bot_id": bot_id})
    if not existing:
        await db.user_roles.insert_one({
            "user_id": user_id,
            "role_id": role_id,
            "bot_id": bot_id,
            "granted_by": str(granting_user["_id"]),
            "created_at": datetime.utcnow(),
        })
    return RedirectResponse(f"/dashboard/bots/{bot_id}/roles", status_code=302)


@router.post("/revoke/{user_role_id}")
async def revoke_role(
    request: Request,
    bot_id: str,
    user_role_id: str,
    user: dict = Depends(require_auth),
):
    db = get_db()
    await db.user_roles.delete_one({"_id": ObjectId(user_role_id)})
    return RedirectResponse(f"/dashboard/bots/{bot_id}/roles", status_code=302)
