# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server (auto-reload)
uvicorn main:app --reload

# Run on specific port
uvicorn main:app --reload --port 8000

# Run for production (Railway uses this)
uvicorn main:app --host 0.0.0.0 --port $PORT
```

No test suite is currently set up. No linter config exists.

## Environment

Copy `.env.example` to `.env` and populate:
- `MONGO_URI` — MongoDB Atlas connection string
- `CLAUDE_API_KEY` — Anthropic API key
- `SECRET_KEY` — Random string for session security
- `SESSION_TTL_HOURS` — Session lifetime (default 24)

## Architecture

**Two-part app**: public customer chat + authenticated manager dashboard.

**Request flow**: `main.py` mounts all routers → `routers/` call `services/` for business logic → `services/` query MongoDB directly via Motor.

### Auth & Sessions
- Login creates a session document in MongoDB; `session_id` stored in an HTTPOnly cookie
- `dependencies.py` provides `require_auth`, `require_creation_role`, and `require_permission(Permission.X)` for FastAPI dependency injection
- Chat routes are fully public and use a separate `chat_session_id` cookie (UUID only, no auth)

### Permission System
- `Permission` is an `IntFlag` bitmap in `models/role.py`
- A user can have multiple roles per bot; effective permissions = bitwise OR of all their role bitmaps
- `has_creation_role` (user-level flag) grants full dashboard access and bypasses per-bot permission checks
- Per-bot permissions govern: KB URL, guidelines, auto-fix toggle, mistake review/approval, role management

### Claude Integration (`services/claude.py`)
- KB content is injected directly into the system prompt (no RAG/vector DB)
- Tool calling: `get_application_status`, `get_transaction_status` (mocked in `services/mock_functions.py`)
- Mistake auto-fix: Claude receives the bad response + complaint and returns updated `additional_guidelines`
- Meta-agent (Part 2, `routers/meta.py`): Claude reads uploaded docs + manager instructions and generates a full bot config

### KB Scraper (`services/kb_scraper.py`)
- Scrapes Zendesk-style help centers, extracts up to 30 articles
- Cached in the `kb_content` collection; re-scrapes only when the KB URL changes on a bot

### Frontend
- Jinja2 templates + HTMX; no JS framework
- Chat uses `hx-post` → returns partial HTML (`templates/chat/messages_partial.html`) that HTMX appends to `#messages`
- Dashboard forms use HTMX for inline updates (settings, role assignments, mistake analysis)

### MongoDB Collections
`users`, `sessions`, `bots`, `roles`, `user_roles`, `kb_content`, `conversations`, `mistakes`, `mistakes_archive`

Indexes are created at startup in `database.py` (unique on `username`, `session_id`, `slug`; TTL on `sessions.expires_at`).
