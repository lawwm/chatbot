import re
from markupsafe import Markup, escape


def render_markdown(text: str) -> Markup:
    """Convert basic markdown to safe HTML."""
    s = str(escape(text))
    # Headers → bold block labels (avoid large h1/h2 in chat bubbles)
    s = re.sub(r'^#{1,6}\s+(.+)$', r'<strong class="md-heading">\1</strong>', s, flags=re.MULTILINE)
    # Bold / italic / code
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    # Bullet lists: - item or * item → • item
    s = re.sub(r'^[ \t]*[-*]\s+(.+)$', r'&nbsp;&nbsp;• \1', s, flags=re.MULTILINE)
    # Numbered lists: 1. item
    s = re.sub(r'^[ \t]*(\d+)\.\s+(.+)$', r'&nbsp;&nbsp;\1. \2', s, flags=re.MULTILINE)
    s = s.replace('\n', '<br>')
    return Markup(s)
