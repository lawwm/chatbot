import re
from markupsafe import Markup, escape


def render_markdown(text: str) -> Markup:
    """Convert basic markdown to safe HTML."""
    s = str(escape(text))
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    s = s.replace('\n', '<br>')
    return Markup(s)
