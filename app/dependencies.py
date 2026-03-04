from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.services.sessions import get_current_user


async def require_auth(request: Request) -> dict:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})
    return user


async def require_creation_role(request: Request) -> dict:
    user = await require_auth(request)
    if not user.get("has_creation_role"):
        raise HTTPException(status_code=403, detail="Requires creation role")
    return user
