from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from datetime import datetime
from app.database import get_db
from app.services.sessions import create_session, delete_session, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and await get_current_user(session_id):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = await db.users.find_one({"username": username})
    if not user or not pwd_context.verify(password, user["password_hash"]):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )
    session_id = await create_session(str(user["_id"]))
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@router.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(session_id)
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie("session_id")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and await get_current_user(session_id):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    existing = await db.users.find_one({"username": username})
    if existing:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Username already taken"},
            status_code=400,
        )
    hashed = pwd_context.hash(password)
    result = await db.users.insert_one({
        "username": username,
        "password_hash": hashed,
        "allow_create_agent": False,
        "created_at": datetime.utcnow(),
    })
    session_id = await create_session(str(result.inserted_id))
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """First-time setup: create the first admin user if no users exist."""
    db = get_db()
    count = await db.users.count_documents({})
    if count > 0:
        return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("auth/setup.html", {"request": request})


@router.post("/setup")
async def setup(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    count = await db.users.count_documents({})
    if count > 0:
        return RedirectResponse("/auth/login", status_code=302)
    hashed = pwd_context.hash(password)
    result = await db.users.insert_one({
        "username": username,
        "password_hash": hashed,
        "allow_create_agent": True,
        "created_at": datetime.utcnow(),
    })
    session_id = await create_session(str(result.inserted_id))
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response
