import secrets
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import get_db
from app.config import settings


async def create_session(user_id: str) -> str:
    db = get_db()
    session_id = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=settings.session_ttl_hours)
    await db.sessions.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
    })
    return session_id


async def get_session(session_id: str) -> dict | None:
    db = get_db()
    session = await db.sessions.find_one({
        "session_id": session_id,
        "expires_at": {"$gt": datetime.utcnow()},
    })
    return session


async def delete_session(session_id: str):
    db = get_db()
    await db.sessions.delete_one({"session_id": session_id})


async def get_current_user(session_id: str) -> dict | None:
    session = await get_session(session_id)
    if not session:
        return None
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(session["user_id"])})
    return user
