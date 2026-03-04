import logging
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
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
