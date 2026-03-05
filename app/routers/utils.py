from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from app.utils import render_markdown

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post("/render-markdown", response_class=HTMLResponse)
async def render_markdown_endpoint(text: str = Form("")):
    return HTMLResponse(render_markdown(text))
