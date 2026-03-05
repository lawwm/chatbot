# Atome Bot Platform — Technical Guide

## Table of Contents

1. [Stack Overview](#stack-overview)
2. [Environment Variables](#environment-variables)
3. [Project Structure](#project-structure)
4. [Running the App](#running-the-app)
5. [MongoDB Collections & Schemas](#mongodb-collections--schemas)
6. [Authentication & Sessions](#authentication--sessions)
7. [Permission System](#permission-system)
8. [Request Flow](#request-flow)
9. [Claude Integration](#claude-integration)
10. [Knowledge Base Pipeline](#knowledge-base-pipeline)
11. [Vector Search](#vector-search)
12. [SSE Scrape Progress Streaming](#sse-scrape-progress-streaming)
13. [Mistake Reporting & Auto-Fix](#mistake-reporting--auto-fix)
14. [Meta Agent](#meta-agent)
15. [Mock Functions](#mock-functions)
16. [Frontend Architecture](#frontend-architecture)
17. [Deployment](#deployment)

---

## Stack Overview

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115.0 (async, ASGI) |
| Server | Uvicorn 0.30.6 |
| Database | MongoDB Atlas (Motor 3.6.0 async driver) |
| AI model | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Meta agent model | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Embeddings | Voyage AI (`voyage-3-lite`, 512 dimensions) |
| Web scraping | Playwright (headless Chromium) + BeautifulSoup4 |
| Templating | Jinja2 |
| Frontend | HTMX 1.9.12 — no JS framework |
| Auth | Server-side sessions (HTTPOnly cookie + MongoDB TTL) |
| Password hashing | passlib + bcrypt |
| Hosting | Railway |

---

## Environment Variables

Defined in `app/config.py` via `pydantic-settings`. Copy `.env.example` to `.env`.

| Variable | Required | Description |
|---|---|---|
| `MONGO_URI` | Yes | MongoDB Atlas connection string |
| `CLAUDE_API_KEY` | Yes | Anthropic API key |
| `SECRET_KEY` | Yes | Random string for session signing |
| `SESSION_TTL_HOURS` | No (default: 24) | Session lifetime in hours |
| `VOYAGE_API_KEY` | No | Voyage AI API key — enables vector search. Without this, KB falls back to full text dump. |

---

## Project Structure

```
main.py                          # App entry point, router mounting, lifespan
app/
  config.py                      # Pydantic settings (env vars)
  database.py                    # MongoDB connect/disconnect, index creation
  dependencies.py                # require_auth, require_creation_role FastAPI deps
  utils.py                       # render_markdown() helper
  models/
    role.py                      # Permission IntFlag enum, Role/UserRole schemas
  routers/
    auth.py                      # Login, logout, first-time setup
    bots.py                      # Bot CRUD, delete bot
    chat.py                      # Public customer chat, mistake reporting
    settings.py                  # Bot config, KB scrape trigger, SSE stream
    mistakes.py                  # Mistake review, analyze, apply fix
    roles.py                     # Role create/assign/delete/revoke
    meta.py                      # Meta-agent chat routes
  services/
    claude.py                    # Claude API: chat(), suggest_fix(), merge_guidelines()
    kb_scraper.py                # Playwright scraper, embed_and_store()
    kb_retrieval.py              # Voyage AI query embedding + $vectorSearch
    scrape_progress.py           # In-memory asyncio queue for SSE
    mock_functions.py            # Mocked get_application_status / get_transaction_status
    meta_agent.py                # Meta-agent: TOOLS, run_agent(), _dispatch_tool()
    permissions.py               # get_user_permission_bitmap(), has_creation_role()
    sessions.py                  # get_current_user()
  templates/
    base.html                    # Shared nav, spinner CSS, modal
    chat/                        # Customer chat UI
    dashboard/                   # Bot settings, mistakes, roles, new bot
    meta/                        # Meta-agent chat UI
    partials/                    # Shared SVG icons etc.
static/
  css/main.css                   # Global styles, .md-content markdown styles
```

---

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Development (auto-reload)
uvicorn main:app --reload

# Specific port
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port $PORT
```

On first run, visit `/auth/setup` to create the initial admin account.

---

## MongoDB Collections & Schemas

**Database name:** `atome`

### `users`
```js
{
  "_id": ObjectId,
  "username": "string",          // unique index
  "password_hash": "string",
  "allow_create_agent": false    // creator role flag
}
```

### `sessions`
```js
{
  "_id": ObjectId,
  "session_id": "uuid-string",   // unique index
  "user_id": "ObjectId_string",
  "expires_at": ISODate,         // TTL index (expireAfterSeconds: 0)
  "created_at": ISODate
}
```

### `bots`
```js
{
  "_id": ObjectId,
  "slug": "my-bot",              // unique index, URL-safe
  "name": "Support Bot",
  "bot_uuid": "a1b2c3d4e",       // 9-char hex, used in chat URL
  "kb_url": "https://...",       // Primary KB URL (legacy)
  "kb_urls": ["url1", "url2"],   // All KB URLs
  "additional_guidelines": "...",
  "auto_fix_enabled": true,
  "allow_override": false,
  "is_public": true,
  "scraper_settings": {
    "max_articles": 30,
    "depth": 1,
    "strategy": "bfs",           // "bfs" | "dfs"
    "delay_ms": 500,
    "timeout_s": 20,
    "max_chars_per_article": 3000
  },
  "system_prompt": "",
  "created_by": "user_id_string",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### `roles`
```js
{
  "_id": ObjectId,
  "name": "Support Agent",
  "bot_id": "ObjectId_string",
  "permission_bitmap": 48,       // OR of Permission bits
  "created_by": "user_id_string",
  "created_at": ISODate
}
```

### `user_roles`
```js
{
  "_id": ObjectId,
  "user_id": "string",
  "role_id": "ObjectId_string",
  "bot_id": "ObjectId_string",
  "granted_by": "user_id_string",
  "created_at": ISODate
}
```

### `kb_content`
```js
{
  "_id": ObjectId,
  "bot_id": "ObjectId_string",
  "kb_urls": ["url1"],
  "articles": [
    {
      "title": "What is Atome Card?",
      "url": "https://...",
      "content": "Full article text..."
    }
  ],
  "scraped_at": ISODate
}
```

### `kb_vectors`
```js
{
  "_id": ObjectId,
  "bot_id": "ObjectId_string",
  "article_url": "https://...",
  "article_title": "FAQ",
  "chunk_index": 0,
  "text": "2000-char chunk...",
  "embedding": [0.12, -0.04, ...]  // 512-dim Voyage AI vector
}
```
**Atlas Vector Search index name:** `vector_index`
**Index config:**
```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 512, "similarity": "cosine" },
    { "type": "filter", "path": "bot_id" }
  ]
}
```

### `conversations`
```js
{
  "_id": ObjectId,
  "bot_id": "ObjectId_string",
  "session_id": "uuid",
  "messages": [
    { "role": "user", "content": "...", "timestamp": ISODate },
    { "role": "assistant", "content": "...", "timestamp": ISODate }
  ],
  "updated_at": ISODate
}
```

### `mistakes`
```js
{
  "_id": ObjectId,
  "bot_id": "ObjectId_string",
  "session_id": "uuid",
  "customer_message": "...",
  "bot_response": "...",
  "complaint": "...",
  "status": "open",
  "suggested_fix": null,           // Populated after analysis
  "merge_result": {                // Populated if conflict detected
    "has_conflict": true,
    "conflict_description": "...",
    "merged": "...",
    "override_version": "...",
    "keep_version": "..."
  },
  "created_at": ISODate
}
```

### `mistakes_archive`
```js
{
  "_id": ObjectId,
  "original_id": "ObjectId_string",
  "bot_id": "ObjectId_string",
  "session_id": "uuid",
  "customer_message": "...",
  "bot_response": "...",
  "complaint": "...",
  "suggested_fix": "...",
  "fix_applied": "full updated guidelines text",
  "fixed_at": ISODate,
  "fixed_by": "auto" | "user_id_string",
  "auto_applied": true
}
```

### `meta_conversations`
```js
{
  "_id": ObjectId,
  "user_id": "string",
  "conv_id": "hex-string",    // unique index
  "title": "First message...",
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "created_at": ISODate,
  "updated_at": ISODate       // compound index: (user_id, updated_at desc)
}
```

---

## Authentication & Sessions

**Login flow** (`app/routers/auth.py`):
1. Lookup user by username
2. Verify password with `passlib.verify`
3. Insert session document into `sessions` collection
4. Set `session_id` cookie (HTTPOnly, SameSite=lax)

**Session validation** (`app/dependencies.py`):
- `require_auth` — validates `session_id` cookie, returns user dict or 401
- `require_creation_role` — same + checks `user.allow_create_agent == True`
- `require_permission(Permission.X)` — validates bitmap for specific permission

**Session expiry:** MongoDB TTL index on `sessions.expires_at` auto-deletes expired documents.

**Public chat** uses a separate `chat_session_id` cookie (UUID only, no auth). Stored as `session_id` in the `conversations` collection.

---

## Permission System

**File:** `app/models/role.py`

```python
class Permission(IntFlag):
    VIEW_SETTINGS   = 1 << 0   # 1
    EDIT_KB_URL     = 1 << 1   # 2
    EDIT_GUIDELINES = 1 << 2   # 4
    TOGGLE_AUTOFIX  = 1 << 3   # 8
    REVIEW_MISTAKES = 1 << 4   # 16
    APPROVE_FIXES   = 1 << 5   # 32
    MANAGE_ROLES    = 1 << 6   # 64
    DELETE_BOT      = 1 << 7   # 128
```

**Effective permissions** = bitwise OR of all `permission_bitmap` values across all `user_roles` documents for `(user_id, bot_id)`.

**Creator users** (`allow_create_agent = True`) bypass all per-bot permission checks and have full access to everything.

**Evaluation** (`app/services/permissions.py`):
```python
async def get_user_permission_bitmap(user_id: str, bot_id: str) -> int:
    # Joins user_roles → roles, ORs all bitmaps
```

---

## Request Flow

### Customer Chat

```
GET /chat/{slug}
  → Load bot by slug
  → Load conversation (chat_session_id cookie + bot_id)
  → Render chat/index.html
  → Set chat_session_id cookie

POST /chat/{slug}/send
  → Load bot + conversation
  → Append user message
  → retrieve_chunks(bot_id, message)         # vector search
    → Falls back to get_kb_content()          # full text dump if empty
  → claude_chat(messages[-20:], kb, guidelines)
      → build_system_prompt(kb, guidelines)
      → client.messages.create(model, tools, messages)
      → Loop:
          stop_reason == "tool_use"  → process_tool_call() → append result → continue
          stop_reason == "end_turn"  → return (text, tool_calls_used)
  → Append assistant message
  → Upsert conversation
  → Return HTMX partial: chat/messages_partial.html

POST /chat/{slug}/report
  → Insert mistake document
  → If bot.auto_fix_enabled → asyncio.create_task(_auto_fix_mistake())
  → Return success banner HTML
```

### Manager Dashboard (Settings Save)

```
POST /dashboard/bots/{bot_id}/settings
  → require_auth + permission check
  → Update bot document (only permitted fields)
  → If kb_urls changed → scrape_progress.start() + asyncio.create_task(scrape_and_store())
  → Redirect to settings page with ?scraping=1

GET /dashboard/bots/{bot_id}/scrape-stream   (SSE)
  → Loop: await scrape_progress.get_event(bot_id, timeout=120)
  → Yield "data: visiting|https://...\n\n"
  → Yield "data: scraped|https://...\n\n"
  → On finish: "data: __done__25\n\n"
  → Close
```

---

## Claude Integration

**File:** `app/services/claude.py`
**Model:** `claude-haiku-4-5-20251001`
**Client:** `anthropic.Anthropic(api_key=settings.claude_api_key)` (synchronous client, called via `asyncio.to_thread` where needed)

### System Prompt

`build_system_prompt(kb_content, additional_guidelines)` produces:

```
You are a helpful customer service assistant for Atome, a Buy Now Pay Later service.

KNOWLEDGE BASE:
{kb_content}

{additional_guidelines}
```

### Tool Definitions

Two tools are registered:

| Tool | Trigger | Required input |
|---|---|---|
| `get_application_status` | Customer asks about application/approval/card status | `customer_id` |
| `get_transaction_status` | Customer reports failed/declined/stuck transaction | `transaction_id` |

### Chat Loop

```python
async def chat(messages, kb_content, additional_guidelines) -> tuple[str, list[dict]]:
    system = build_system_prompt(kb_content, additional_guidelines)
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in messages[-20:]]

    while True:
        response = client.messages.create(model=..., tools=TOOLS, messages=claude_messages)

        if response.stop_reason == "end_turn":
            return text, tool_calls_used

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    result = process_tool_call(block.name, block.input)
                    tool_calls_used.append({"name": block.name, "input": block.input})
            claude_messages.append({"role": "assistant", "content": response.content})
            claude_messages.append({"role": "user", "content": tool_results})
```

### Other Claude Functions

| Function | Model | Max tokens | Purpose |
|---|---|---|---|
| `suggest_fix()` | Haiku | 512 | Generate updated guidelines from a reported mistake |
| `merge_guidelines()` | Haiku | 1024 | Detect conflicts between fix and existing guidelines |
| `generate_bot_config()` | Haiku | 1024 | Meta-agent: generate bot config from doc + instructions |

---

## Knowledge Base Pipeline

**File:** `app/services/kb_scraper.py`

### Scrape Flow

```
scrape_and_store(bot_id, kb_urls, scraper_settings)
  → Delete old kb_content for bot
  → For each URL:
      _scrape(url, settings, on_progress)
        → async_playwright → chromium.launch(headless=True)
        → BFS/DFS crawl queue, same-domain only
        → page.goto(url, wait_until="domcontentloaded")
        → BeautifulSoup parse page.content()
        → Extract title: h1 or <title>
        → Extract content: priority selectors (main, article, .article-body, ...)
        → Remove noise tags: nav, header, footer, script, style, ...
        → Remove by class/id patterns: nav, menu, sidebar, cookie, banner, ...
        → Deduplicate lines, join, limit to max_chars
        → Push progress event via scrape_progress.push()
  → Insert into kb_content collection
  → _embed_and_store(bot_id, articles)
      → _chunk_text(content, size=2000, overlap=200)
      → voyageai.AsyncClient.embed(texts, model="voyage-3-lite", input_type="document")
      → Insert chunks + embeddings into kb_vectors collection
```

### Content Selectors (priority order)

```python
_CONTENT_SELECTORS = [
    "main", "article", "[role='main']",
    ".article-body", ".entry-content", ".post-content",
    ".content", ".main-content", ".page-content",
    "#content", "#main", "#main-content",
]
```

Falls back to `<body>` if none match.

---

## Vector Search

**File:** `app/services/kb_retrieval.py`

```python
async def retrieve_chunks(bot_id: str, query: str, top_k: int = 10) -> str:
    # 1. Embed query
    result = await voyageai_client.embed([query], model="voyage-3-lite", input_type="query")
    query_vector = result.embeddings[0]

    # 2. Atlas $vectorSearch with bot_id filter
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 150,
                "limit": top_k,
                "filter": {"bot_id": {"$eq": bot_id}},
            }
        },
        {"$project": {"text": 1, "score": {"$meta": "vectorSearchScore"}, "_id": 0}},
    ]

    # 3. Fallback: unfiltered search + manual filter if Atlas filter returns nothing
    # 4. Return chunks joined with "\n\n---\n\n"
```

**Fallback chain:**
1. Vector search with `bot_id` filter → if empty:
2. Vector search without filter, manual filter by bot_id → if empty:
3. `get_kb_content()` → full article text dump from `kb_content` collection

---

## SSE Scrape Progress Streaming

**File:** `app/services/scrape_progress.py`

In-memory asyncio queue per `bot_id`. The scraper pushes events; the SSE endpoint drains them.

```python
# Scraper side (kb_scraper.py)
await scrape_progress.push(bot_id, url, "visiting" | "scraped" | "failed")
await scrape_progress.finish(bot_id, article_count=25)

# SSE endpoint side (settings.py)
async def event_generator():
    while True:
        event = await scrape_progress.get_event(bot_id, timeout=120)
        if event.get("done"):
            yield f"data: __done__{event['article_count']}\n\n"
            break
        yield f"data: {event['status']}|{event['url']}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Browser side:** `new EventSource('/dashboard/bots/{id}/scrape-stream')` parses the `data:` events and updates the progress UI.

---

## Mistake Reporting & Auto-Fix

### Reporting (public, no auth)

`POST /chat/{slug}/report` — inserts into `mistakes` collection with `status: "open"`.

### Auto-Fix Background Task

Triggered if `bot.auto_fix_enabled == True`:

```
asyncio.create_task(_auto_fix_mistake(bot_id, mistake_id, bot))
  → suggest_fix(current_guidelines, customer_msg, bot_response, complaint)
      → Claude Haiku prompt → returns updated guidelines text
  → merge_guidelines(existing, fix)
      → Claude Haiku prompt → returns JSON:
         { has_conflict, conflict_description, merged, override_version, keep_version }
  → If no conflict OR allow_override:
      → Update bot.additional_guidelines
      → Insert into mistakes_archive (fixed_by: "auto")
      → Delete from mistakes
  → If conflict AND NOT allow_override:
      → Save suggested_fix + merge_result to mistakes document (awaits manual review)
```

### Manual Review (`/dashboard/bots/{id}/mistakes`)

- **Analyze & Suggest Fix** → `POST .../analyze` → calls same `suggest_fix()` + `merge_guidelines()`
- **Apply Fix** → `POST .../apply` → updates bot guidelines, archives mistake, fires `mistakeArchived` HTMX event
- **Archive section** auto-refreshes via HTMX trigger

---

## Meta Agent

**File:** `app/services/meta_agent.py`
**System prompt:** `app/services/meta_prompt.md`
**Model:** `claude-haiku-4-5-20251001`
**Max tokens:** 2048

### Tools (15 total)

| Tool | Action |
|---|---|
| `list_bots` | List bots accessible to user |
| `get_bot_settings` | Get full bot config |
| `update_bot_settings` | Update any bot config field |
| `trigger_scrape` | Start KB scrape in background |
| `list_mistakes` | List open mistakes for a bot |
| `analyze_mistake` | Run suggest_fix + merge_guidelines |
| `apply_fix` | Apply fix, archive mistake |
| `dismiss_mistake` | Delete mistake without fix |
| `list_roles` | List roles + user assignments |
| `create_role` | Create role with permission list |
| `assign_role` | Assign role to user by username |
| `delete_role` | Delete role + all assignments |
| `revoke_role` | Remove one user's role assignment |
| `create_bot` | Create new bot |
| `delete_bot` | Permanently delete bot + all data |

### Agent Loop

```python
async def run_agent(user_id, conv_id, user_message) -> tuple[str, list[dict]]:
    # Load stored conversation (text only — no tool_use blocks stored)
    # Append user message
    # Rebuild API messages from stored history

    while True:
        response = await asyncio.to_thread(client.messages.create, ...)
        if response.stop_reason == "end_turn": break
        if response.stop_reason == "tool_use":
            for block in response.content:
                tool_calls_made.append({"name": block.name, "input": dict(block.input)})
                result = await _dispatch_tool(block.name, block.input, user_id)
            api_messages.append({"role": "assistant", "content": response.content})
            api_messages.append({"role": "user", "content": tool_results})

    # Persist text messages only (strips tool_use blocks from stored history)
    # Upsert meta_conversations document
    return assistant_text, tool_calls_made
```

Conversation history is stored as plain text turns (tool blocks are not persisted — they are reconstructed per-turn in `api_messages` but not saved to MongoDB).

---

## Mock Functions

**File:** `app/services/mock_functions.py`

Both functions use deterministic hashing on the input ID so the same ID always returns the same result in demos.

```python
def get_application_status(customer_id: str) -> dict:
    # Returns: {"customer_id": ..., "status": "approved|pending|rejected|more_info_required", ...}

def get_transaction_status(transaction_id: str) -> dict:
    # Returns: {"transaction_id": ..., "status": "failed|processing", "reason": "...", ...}
```

To connect real data sources, replace the implementations in this file. The tool schemas in `app/services/claude.py` (`TOOLS`) and the dispatch in `process_tool_call()` do not need to change.

---

## Frontend Architecture

- **No JS framework.** All interactivity is HTMX + vanilla JS.
- **HTMX patterns used:**
  - `hx-post` + `hx-target` + `hx-swap="beforeend"` — append chat bubbles
  - `hx-swap-oob="innerHTML"` — update the scrape panel out-of-band
  - `HX-Trigger` response header — fire custom JS events (`mistakeArchived`, `metaNewConv`)
  - `HX-Push-Url` response header — update browser URL without reload
  - `htmx-request` CSS class — auto spinner on HTMX buttons
- **Markdown rendering:**
  - Server-side: Python `markdown` library with `tables`, `fenced_code`, `nl2br` extensions (`app/utils.py`)
  - Client-side (guidelines preview only): `marked.js` from CDN
- **Spinner system:** Global CSS `::after` pseudo-element on `.btn.htmx-request` and `.btn-loading`
- **SSE:** Native browser `EventSource` API for scrape progress

---

## Deployment

### Railway

Railway auto-detects the Python app. Set environment variables in Railway dashboard:

```
MONGO_URI=mongodb+srv://...
CLAUDE_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
SECRET_KEY=<random-string>
SESSION_TTL_HOURS=24
```

Start command:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Atlas Vector Search Index

Create a Search Index on the `kb_vectors` collection named `vector_index`:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 512,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "bot_id"
    }
  ]
}
```

### First-Time Setup

1. Start the server
2. Visit `/auth/setup` — create the first admin account
3. Log in at `/auth/login`
4. Go to `/dashboard/bots/new` and create your first bot

---

*For user-facing documentation, see [USER_GUIDE.md](./USER_GUIDE.md).*
