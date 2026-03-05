import markdown as _md
from markupsafe import Markup

_MD = _md.Markdown(extensions=["tables", "fenced_code", "nl2br"])


def render_markdown(text: str) -> Markup:
    """Convert markdown to safe HTML (tables, fenced code, bold, italic, lists)."""
    _MD.reset()
    return Markup(_MD.convert(str(text)))
