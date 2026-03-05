from app.database import get_db
from app.models.role import Permission
from bson import ObjectId


async def get_user_permission_bitmap(user_id: str, bot_id: str) -> int:
    """Returns the OR combination of all permission bitmaps for a user on a given bot."""
    db = get_db()
    user_roles = await db.user_roles.find({"user_id": user_id, "bot_id": bot_id}).to_list(None)
    if not user_roles:
        return 0
    role_ids = [ObjectId(ur["role_id"]) for ur in user_roles]
    roles = await db.roles.find({"_id": {"$in": role_ids}}).to_list(None)
    bitmap = 0
    for role in roles:
        bitmap |= role.get("permission_bitmap", 0)
    return bitmap


async def has_permission(user_id: str, bot_id: str, permission: Permission) -> bool:
    bitmap = await get_user_permission_bitmap(user_id, bot_id)
    return bool(bitmap & permission)


async def has_creation_role(user: dict) -> bool:
    return user.get("allow_create_agent", False)


def require_permission(permission: Permission):
    """Returns a dependency that checks a user has a given permission for a bot."""
    from fastapi import Request, HTTPException
    from app.services.sessions import get_current_user

    async def checker(request: Request, bot_id: str):
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user = await get_current_user(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if not await has_permission(str(user["_id"]), bot_id, permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker
