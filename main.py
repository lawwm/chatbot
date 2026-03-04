import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from app.database import connect, disconnect
from app.routers import auth, chat, bots, settings, mistakes, roles, meta


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await disconnect()


app = FastAPI(title="Atome Customer Service Bot", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    session_id = request.cookies.get("session_id")
    user = None
    if session_id:
        from app.services.sessions import get_current_user
        user = await get_current_user(session_id)
    return templates.TemplateResponse(
        "404.html", {"request": request, "user": user}, status_code=404
    )

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(bots.router)
app.include_router(settings.router)
app.include_router(mistakes.router)
app.include_router(roles.router)
app.include_router(meta.router)


@app.get("/")
async def root(request: Request):
    db_module = __import__("app.database", fromlist=["get_db"])
    db = db_module.get_db()
    count = await db.users.count_documents({})
    if count == 0:
        return RedirectResponse("/auth/setup")
    return RedirectResponse("/bots")
