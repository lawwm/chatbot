import asyncio
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

import anthropic
from bson import ObjectId

from app.config import settings
from app.database import get_db
from app.models.role import Permission
from app.services.claude import suggest_fix, merge_guidelines

client = anthropic.Anthropic(api_key=settings.claude_api_key)

_PROMPT_FILE = Path(__file__).parent / "meta_prompt.md"
SYSTEM_PROMPT = _PROMPT_FILE.read_text(encoding="utf-8")

TOOLS = [
    {
        "name": "list_bots",
        "description": (
            "MUST call this tool when the user asks to see their bots, mentions 'my bots', "
            "asks what bots exist, or needs a bot_id you do not already have. "
            "You cannot know what bots exist without calling this. Returns name, id, and slug for each bot."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_bot_settings",
        "description": (
            "MUST call this tool before showing settings, before updating anything, or whenever the user asks "
            "about a bot's current configuration. You do not know the current settings without calling this. "
            "Provide bot_id if known, otherwise provide bot_name for a partial name match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "bot_name": {"type": "string", "description": "Partial bot name. Use when bot_id is not known."},
            },
            "required": [],
        },
    },
    {
        "name": "update_bot_settings",
        "description": (
            "MUST call this tool to save any change to a bot's settings. "
            "Call get_bot_settings first if you do not already have the bot_id. "
            "Only include the fields you are changing — omit everything else."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "kb_urls": {"type": "array", "items": {"type": "string"}, "description": "Full list of KB URLs to set."},
                "additional_guidelines": {"type": "string", "description": "Full guidelines text to save."},
                "auto_fix_enabled": {"type": "boolean", "description": "Enable or disable auto-fix."},
                "allow_override": {"type": "boolean", "description": "Allow auto-fix to override conflicting guidelines."},
                "is_public": {"type": "boolean", "description": "Make the bot publicly accessible."},
                "scraper_settings": {
                    "type": "object",
                    "description": "Scraper config. Keys: max_articles (int), depth (int), strategy ('bfs'|'dfs'), delay_ms (int), timeout_s (int), max_chars_per_article (int).",
                },
            },
            "required": ["bot_id"],
        },
    },
    {
        "name": "trigger_scrape",
        "description": (
            "MUST call this tool when the user asks to scrape, re-scrape, populate, or refresh the knowledge base. "
            "Runs in the background using the bot's saved kb_urls and scraper_settings. "
            "Call get_bot_settings first if you need to confirm what URLs will be scraped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
            },
            "required": ["bot_id"],
        },
    },
    {
        "name": "list_mistakes",
        "description": (
            "MUST call this tool when the user asks to see mistakes, complaints, or reported errors for a bot. "
            "You cannot know what mistakes exist without calling this. Returns open (unresolved) mistakes only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
            },
            "required": ["bot_id"],
        },
    },
    {
        "name": "analyze_mistake",
        "description": (
            "MUST call this tool when the user wants to analyze a mistake, get a suggested fix, or see what guideline change is recommended. "
            "Call list_mistakes first if you do not have the mistake_id. "
            "Returns a suggested fix text and whether it conflicts with existing guidelines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "mistake_id": {"type": "string", "description": "MongoDB ObjectId string of the mistake."},
            },
            "required": ["bot_id", "mistake_id"],
        },
    },
    {
        "name": "apply_fix",
        "description": (
            "MUST call this tool to apply an approved fix: updates the bot's guidelines and archives the mistake. "
            "Always show the user the new_guidelines text and get explicit confirmation before calling. "
            "Call analyze_mistake first if suggested fix text is not yet available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "mistake_id": {"type": "string", "description": "MongoDB ObjectId string of the mistake."},
                "new_guidelines": {"type": "string", "description": "The complete updated guidelines text to save."},
            },
            "required": ["bot_id", "mistake_id", "new_guidelines"],
        },
    },
    {
        "name": "dismiss_mistake",
        "description": (
            "MUST call this tool to delete a mistake without applying any fix. "
            "Always confirm with the user before calling — this permanently removes the mistake."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mistake_id": {"type": "string", "description": "MongoDB ObjectId string of the mistake."},
            },
            "required": ["mistake_id"],
        },
    },
    {
        "name": "list_roles",
        "description": (
            "MUST call this tool when the user asks about roles, permissions, or who has access to a bot. "
            "You cannot know the roles or assignments without calling this. "
            "Also call this before creating, assigning, or deleting roles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
            },
            "required": ["bot_id"],
        },
    },
    {
        "name": "create_role",
        "description": (
            "MUST call this tool to create a new role with specific permissions for a bot. "
            "Valid permission names: VIEW_SETTINGS, EDIT_KB_URL, EDIT_GUIDELINES, "
            "TOGGLE_AUTOFIX, REVIEW_MISTAKES, APPROVE_FIXES, MANAGE_ROLES, DELETE_BOT."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "role_name": {"type": "string", "description": "Display name for the role."},
                "permissions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of permission names to grant. Valid values: VIEW_SETTINGS, EDIT_KB_URL, EDIT_GUIDELINES, TOGGLE_AUTOFIX, REVIEW_MISTAKES, APPROVE_FIXES, MANAGE_ROLES, DELETE_BOT.",
                },
            },
            "required": ["bot_id", "role_name", "permissions"],
        },
    },
    {
        "name": "assign_role",
        "description": (
            "MUST call this tool to assign a role to a user by username. "
            "Call list_roles first if you do not have the role_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role_id": {"type": "string", "description": "MongoDB ObjectId string of the role."},
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
                "username": {"type": "string", "description": "Username of the user to assign the role to."},
            },
            "required": ["role_id", "bot_id", "username"],
        },
    },
    {
        "name": "delete_role",
        "description": (
            "MUST call this tool to delete a role and remove all its user assignments. "
            "Always confirm with the user before calling — this is irreversible. "
            "Call list_roles first if you do not have the role_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role_id": {"type": "string", "description": "MongoDB ObjectId string of the role."},
            },
            "required": ["role_id"],
        },
    },
    {
        "name": "revoke_role",
        "description": (
            "MUST call this tool to remove a specific role assignment from a user. "
            "Call list_roles first to get the user_role_id — it is listed under each role's assignments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_role_id": {"type": "string", "description": "MongoDB ObjectId string from the user_roles collection."},
            },
            "required": ["user_role_id"],
        },
    },
    {
        "name": "create_bot",
        "description": (
            "MUST call this tool when the user asks to create a new bot. "
            "Ask for the bot name if not provided. "
            "After calling, immediately call get_bot_settings to show the created bot's full details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The bot name."},
                "kb_url": {"type": "string", "description": "Optional knowledge base URL. If provided, a scrape starts automatically."},
                "additional_guidelines": {"type": "string", "description": "Optional initial guidelines text."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "delete_bot",
        "description": (
            "MUST call this tool to permanently delete a bot and ALL its data: settings, KB content, vectors, conversations, mistakes, and roles. "
            "This is irreversible. Always show the user the bot name and explicitly ask for confirmation before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "MongoDB ObjectId string of the bot."},
            },
            "required": ["bot_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _find_bot(db, bot_id: str = None, bot_name: str = None):
    if bot_id:
        try:
            return await db.bots.find_one({"_id": ObjectId(bot_id)})
        except Exception:
            pass
    if bot_name:
        return await db.bots.find_one({"name": {"$regex": bot_name, "$options": "i"}})
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _tool_list_bots(inp: dict, user_id: str) -> str:
    db = get_db()
    user_roles = await db.user_roles.find({"user_id": user_id}).to_list(None)
    role_bot_ids = [ObjectId(ur["bot_id"]) for ur in user_roles]
    bots = await db.bots.find({
        "$or": [
            {"created_by": user_id},
            {"_id": {"$in": role_bot_ids}},
            {"is_public": True},
        ]
    }).to_list(None)
    if not bots:
        return "No bots found."
    lines = [f"- {b['name']}  (id: {b['_id']}, slug: {b.get('slug', '')})" for b in bots]
    return "Bots you have access to:\n" + "\n".join(lines)


async def _tool_get_bot_settings(inp: dict, user_id: str) -> str:
    db = get_db()
    bot = await _find_bot(db, inp.get("bot_id"), inp.get("bot_name"))
    if not bot:
        return "Bot not found. Please provide a valid bot name or id."
    kb_urls = bot.get("kb_urls") or [bot.get("kb_url", "")]
    return (
        f"Bot: {bot['name']}  (id: {bot['_id']})\n"
        f"Slug: {bot.get('slug', '')}\n"
        f"KB URLs: {kb_urls}\n"
        f"Guidelines: {bot.get('additional_guidelines') or '(none)'}\n"
        f"Auto-fix: {bot.get('auto_fix_enabled', False)}\n"
        f"Allow override: {bot.get('allow_override', False)}\n"
        f"Is public: {bot.get('is_public', False)}\n"
        f"Scraper settings: {bot.get('scraper_settings', {})}"
    )


async def _tool_update_bot_settings(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    try:
        bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    except Exception:
        return f"Invalid bot_id: {bot_id}"
    if not bot:
        return "Bot not found."

    update: dict = {"updated_at": datetime.utcnow()}
    changed = []

    if "kb_urls" in inp:
        update["kb_urls"] = inp["kb_urls"]
        if inp["kb_urls"]:
            update["kb_url"] = inp["kb_urls"][0]
        changed.append("kb_urls")
    if "additional_guidelines" in inp:
        update["additional_guidelines"] = inp["additional_guidelines"]
        changed.append("additional_guidelines")
    if "auto_fix_enabled" in inp:
        update["auto_fix_enabled"] = inp["auto_fix_enabled"]
        changed.append("auto_fix_enabled")
    if "allow_override" in inp:
        update["allow_override"] = inp["allow_override"]
        changed.append("allow_override")
    if "is_public" in inp:
        update["is_public"] = inp["is_public"]
        changed.append("is_public")
    if "scraper_settings" in inp:
        update["scraper_settings"] = inp["scraper_settings"]
        changed.append("scraper_settings")

    if not changed:
        return "No fields to update were provided."

    await db.bots.update_one({"_id": ObjectId(bot_id)}, {"$set": update})
    return f"Updated {', '.join(changed)} for bot '{bot['name']}'."


async def _tool_trigger_scrape(inp: dict, user_id: str) -> str:
    from app.services import scrape_progress
    from app.services.kb_scraper import scrape_and_store

    db = get_db()
    bot_id = inp.get("bot_id", "")
    try:
        bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    except Exception:
        return f"Invalid bot_id: {bot_id}"
    if not bot:
        return "Bot not found."

    kb_urls = [u for u in (bot.get("kb_urls") or [bot.get("kb_url", "")]) if u]
    if not kb_urls:
        return "Bot has no KB URLs configured. Update kb_urls first."

    scraper_settings = bot.get("scraper_settings", {})
    scrape_progress.start(bot_id)

    async def _run():
        try:
            await scrape_and_store(bot_id, kb_urls, scraper_settings)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Meta-agent scrape failed bot=%s: %s", bot_id, e)
            await scrape_progress.finish(bot_id, article_count=0)

    asyncio.create_task(_run())
    return f"Scrape started for bot '{bot['name']}' ({len(kb_urls)} URL(s)). It runs in the background."


async def _tool_list_mistakes(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    mistakes = await db.mistakes.find(
        {"bot_id": bot_id, "status": {"$ne": "archived"}}
    ).sort("created_at", -1).to_list(None)
    if not mistakes:
        return "No open mistakes found for this bot."
    lines = []
    for m in mistakes:
        lines.append(
            f"- id: {m['_id']}\n"
            f"  Customer said: {m.get('customer_message', '')[:80]}\n"
            f"  Complaint: {m.get('complaint', '')[:80]}"
        )
    return f"{len(mistakes)} open mistake(s):\n" + "\n".join(lines)


async def _tool_analyze_mistake(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    mistake_id = inp.get("mistake_id", "")
    try:
        mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
    except Exception:
        return f"Invalid mistake_id: {mistake_id}"
    if not mistake:
        return "Mistake not found."

    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    current_guidelines = (bot.get("additional_guidelines") or "") if bot else ""

    fix = await suggest_fix(
        current_guidelines,
        mistake["customer_message"],
        mistake["bot_response"],
        mistake["complaint"],
    )
    merge_result = await merge_guidelines(current_guidelines, fix)

    await db.mistakes.update_one(
        {"_id": ObjectId(mistake_id)},
        {"$set": {"suggested_fix": fix, "merge_result": merge_result}},
    )

    if merge_result["has_conflict"]:
        return (
            f"Suggested fix generated, but it CONFLICTS with existing guidelines.\n"
            f"Conflict: {merge_result['conflict_description']}\n\n"
            f"Override version (fix takes precedence):\n{merge_result['override_version'][:400]}\n\n"
            f"Keep version (existing instruction wins):\n{merge_result['keep_version'][:400]}\n\n"
            f"Call apply_fix with your chosen version text."
        )
    return (
        f"Suggested fix (no conflict detected):\n{merge_result['merged']}\n\n"
        f"Call apply_fix with bot_id={bot_id}, mistake_id={mistake_id} and the above text to apply it."
    )


async def _tool_apply_fix(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    mistake_id = inp.get("mistake_id", "")
    new_guidelines = inp.get("new_guidelines", "")
    try:
        mistake = await db.mistakes.find_one({"_id": ObjectId(mistake_id)})
    except Exception:
        return f"Invalid mistake_id: {mistake_id}"
    if not mistake:
        return "Mistake not found."

    await db.bots.update_one(
        {"_id": ObjectId(bot_id)},
        {"$set": {"additional_guidelines": new_guidelines, "updated_at": datetime.utcnow()}},
    )
    await db.mistakes_archive.insert_one({
        "original_id": mistake_id,
        "bot_id": bot_id,
        "session_id": mistake.get("session_id", ""),
        "customer_message": mistake["customer_message"],
        "bot_response": mistake["bot_response"],
        "complaint": mistake["complaint"],
        "suggested_fix": mistake.get("suggested_fix", new_guidelines),
        "fix_applied": new_guidelines,
        "fixed_at": datetime.utcnow(),
        "fixed_by": user_id,
        "auto_applied": False,
    })
    await db.mistakes.delete_one({"_id": ObjectId(mistake_id)})
    return "Fix applied. Bot guidelines updated and mistake archived."


async def _tool_dismiss_mistake(inp: dict, user_id: str) -> str:
    db = get_db()
    mistake_id = inp.get("mistake_id", "")
    try:
        result = await db.mistakes.delete_one({"_id": ObjectId(mistake_id)})
    except Exception:
        return f"Invalid mistake_id: {mistake_id}"
    if result.deleted_count == 0:
        return "Mistake not found or already dismissed."
    return "Mistake dismissed (deleted without applying a fix)."


async def _tool_list_roles(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    roles = await db.roles.find({"bot_id": bot_id}).to_list(None)
    if not roles:
        return "No roles found for this bot."
    lines = []
    for r in roles:
        role_id = str(r["_id"])
        bitmap = r.get("permission_bitmap", 0)
        perms = [p.name for p in Permission if p & bitmap] or ["(none)"]
        assignments = await db.user_roles.find({"role_id": role_id}).to_list(None)
        user_ids = [a["user_id"] for a in assignments]
        # Resolve usernames
        usernames = []
        for uid in user_ids:
            try:
                u = await db.users.find_one({"_id": ObjectId(uid)})
                usernames.append(u["username"] if u else uid)
            except Exception:
                usernames.append(uid)
        assigned_str = ", ".join(
            f"{u} (assignment_id: {str(assignments[i]['_id'])})"
            for i, u in enumerate(usernames)
        ) if usernames else "(none)"
        lines.append(
            f"- Role: {r['name']}  (id: {role_id})\n"
            f"  Permissions: {', '.join(perms)}\n"
            f"  Assigned to: {assigned_str}"
        )
    return "\n".join(lines)


async def _tool_create_role(inp: dict, user_id: str) -> str:
    db = get_db()
    bot_id = inp.get("bot_id", "")
    role_name = inp.get("role_name", "")
    permissions = inp.get("permissions", [])

    bitmap = 0
    for pname in permissions:
        try:
            bitmap |= Permission[pname].value
        except KeyError:
            valid = [p.name for p in Permission]
            return f"Unknown permission '{pname}'. Valid names: {valid}"

    result = await db.roles.insert_one({
        "name": role_name,
        "bot_id": bot_id,
        "permission_bitmap": bitmap,
        "created_by": user_id,
        "created_at": datetime.utcnow(),
    })
    return f"Role '{role_name}' created (id: {result.inserted_id}, permissions bitmap: {bitmap})."


async def _tool_assign_role(inp: dict, user_id: str) -> str:
    db = get_db()
    role_id = inp.get("role_id", "")
    bot_id = inp.get("bot_id", "")
    username = inp.get("username", "")

    target = await db.users.find_one({"username": username})
    if not target:
        return f"User '{username}' not found."

    target_user_id = str(target["_id"])
    existing = await db.user_roles.find_one({"user_id": target_user_id, "role_id": role_id})
    if existing:
        return f"User '{username}' already has this role."

    await db.user_roles.insert_one({
        "user_id": target_user_id,
        "role_id": role_id,
        "bot_id": bot_id,
        "granted_by": user_id,
        "created_at": datetime.utcnow(),
    })
    return f"Role assigned to '{username}'."


async def _tool_delete_role(inp: dict, user_id: str) -> str:
    db = get_db()
    role_id = inp.get("role_id", "")
    try:
        result = await db.roles.delete_one({"_id": ObjectId(role_id)})
    except Exception:
        return f"Invalid role_id: {role_id}"
    if result.deleted_count == 0:
        return "Role not found."
    await db.user_roles.delete_many({"role_id": role_id})
    return "Role deleted and all user assignments revoked."


async def _tool_revoke_role(inp: dict, user_id: str) -> str:
    db = get_db()
    user_role_id = inp.get("user_role_id", "")
    try:
        result = await db.user_roles.delete_one({"_id": ObjectId(user_role_id)})
    except Exception:
        return f"Invalid user_role_id: {user_role_id}"
    if result.deleted_count == 0:
        return "Assignment not found."
    return "Role assignment revoked."


async def _tool_create_bot(inp: dict, user_id: str) -> str:
    from app.services import scrape_progress
    from app.services.kb_scraper import scrape_and_store

    db = get_db()
    name = inp.get("name", "").strip()
    kb_url = inp.get("kb_url", "").strip()
    from app.routers.bots import DEFAULT_GUIDELINES
    guidelines = inp.get("additional_guidelines", DEFAULT_GUIDELINES)

    if not name:
        return "Bot name is required."

    kb_urls = [kb_url] if kb_url else []

    slug = _slugify(name)
    base_slug = slug
    counter = 1
    while await db.bots.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    scraper_settings = {
        "max_articles": 30,
        "depth": 1,
        "strategy": "bfs",
        "delay_ms": 500,
        "timeout_s": 20,
        "max_chars_per_article": 2**31 - 1,
    }

    result = await db.bots.insert_one({
        "name": name,
        "slug": slug,
        "bot_uuid": uuid.uuid4().hex[:9],
        "kb_url": kb_url,
        "kb_urls": kb_urls,
        "scraper_settings": scraper_settings,
        "additional_guidelines": guidelines,
        "auto_fix_enabled": False,
        "allow_override": False,
        "is_public": False,
        "system_prompt": "",
        "created_by": user_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    bot_id = str(result.inserted_id)

    # Grant creator full permissions via a role
    role_result = await db.roles.insert_one({
        "name": f"all-perms-{name}",
        "bot_id": bot_id,
        "permission_bitmap": Permission.all(),
        "created_by": user_id,
        "created_at": datetime.utcnow(),
    })
    await db.user_roles.insert_one({
        "user_id": user_id,
        "role_id": str(role_result.inserted_id),
        "bot_id": bot_id,
        "granted_by": user_id,
        "created_at": datetime.utcnow(),
    })

    scrape_note = ""
    if kb_urls:
        scrape_progress.start(bot_id)

        async def _run():
            try:
                await scrape_and_store(bot_id, kb_urls, scraper_settings)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    "Meta-agent scrape on create failed bot=%s: %s", bot_id, e
                )
                await scrape_progress.finish(bot_id, article_count=0)

        asyncio.create_task(_run())
        scrape_note = " KB scrape started in background."
    else:
        scrape_note = " No KB URL provided — add one and trigger a scrape when ready."

    return f"Bot '{name}' created (id: {bot_id}, slug: {slug}).{scrape_note}"


async def _tool_delete_bot(inp: dict, user_id: str) -> str:
    bot_id = inp.get("bot_id", "").strip()
    if not bot_id:
        return "bot_id is required."
    db = get_db()
    bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        return f"No bot found with id '{bot_id}'."
    bot_name = bot.get("name", bot_id)
    # Delete all associated data
    await db.bots.delete_one({"_id": ObjectId(bot_id)})
    await db.kb_content.delete_many({"bot_id": bot_id})
    await db.kb_vectors.delete_many({"bot_id": bot_id})
    await db.conversations.delete_many({"bot_id": bot_id})
    await db.mistakes.delete_many({"bot_id": bot_id})
    await db.mistakes_archive.delete_many({"bot_id": bot_id})
    # Delete roles and assignments
    roles = await db.roles.find({"bot_id": bot_id}).to_list(None)
    role_ids = [str(r["_id"]) for r in roles]
    if role_ids:
        await db.user_roles.delete_many({"role_id": {"$in": role_ids}})
    await db.roles.delete_many({"bot_id": bot_id})
    await db.user_roles.delete_many({"bot_id": bot_id})
    return f"Bot '{bot_name}' (id: {bot_id}) and all associated data have been permanently deleted."


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "list_bots": _tool_list_bots,
    "get_bot_settings": _tool_get_bot_settings,
    "update_bot_settings": _tool_update_bot_settings,
    "trigger_scrape": _tool_trigger_scrape,
    "list_mistakes": _tool_list_mistakes,
    "analyze_mistake": _tool_analyze_mistake,
    "apply_fix": _tool_apply_fix,
    "dismiss_mistake": _tool_dismiss_mistake,
    "list_roles": _tool_list_roles,
    "create_role": _tool_create_role,
    "assign_role": _tool_assign_role,
    "delete_role": _tool_delete_role,
    "revoke_role": _tool_revoke_role,
    "create_bot": _tool_create_bot,
    "delete_bot": _tool_delete_bot,
}


async def _dispatch_tool(name: str, inp: dict, user_id: str) -> str:
    log.warning("META TOOL CALL >>> name=%s | user_id=%s | input=%s", name, user_id, inp)
    handler = _TOOL_MAP.get(name)
    if not handler:
        log.warning("META TOOL CALL >>> unknown tool: %s", name)
        return f"Unknown tool: {name}"
    try:
        result = await handler(inp, user_id)
        log.warning("META TOOL RESULT >>> name=%s | result=%s", name, result)
        return result
    except Exception as e:
        log.warning("META TOOL ERROR >>> name=%s | error=%s", name, e)
        return f"Tool error ({name}): {e}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

async def run_agent(user_id: str, conv_id: str, user_message: str) -> tuple[str, list[str]]:
    """Run the meta-agent for one user turn. Returns (assistant_text, tool_names_called)."""
    db = get_db()

    # Load stored conversation (text turns only)
    conv = await db.meta_conversations.find_one({"conv_id": conv_id})
    stored_messages: list[dict] = conv.get("messages", []) if conv else []

    # Auto-set title from first user message
    is_first_message = len(stored_messages) == 0
    title = conv.get("title", "New chat") if conv else "New chat"
    if is_first_message:
        title = user_message[:45].strip() + ("…" if len(user_message) > 45 else "")

    # Append the new user message to stored history
    stored_messages.append({"role": "user", "content": user_message})

    # Build the API message list from stored text history
    api_messages: list = [{"role": m["role"], "content": m["content"]} for m in stored_messages]

    assistant_text = "I'm sorry, I couldn't process that request."
    tool_names: list[str] = []

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=api_messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    assistant_text = block.text
                    break
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_names.append(block.name)
                    result = await _dispatch_tool(block.name, block.input, user_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            # Append tool use + results to api_messages for the next loop
            api_messages.append({"role": "assistant", "content": response.content})
            api_messages.append({"role": "user", "content": tool_results})
            continue

        # Fallback for unexpected stop reasons
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text = block.text
                break
        break

    # Persist the assistant's text reply to stored history
    stored_messages.append({"role": "assistant", "content": assistant_text})

    await db.meta_conversations.update_one(
        {"conv_id": conv_id},
        {"$set": {
            "user_id": user_id,
            "conv_id": conv_id,
            "title": title,
            "messages": stored_messages,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )

    return assistant_text, tool_names
