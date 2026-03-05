import json
import logging
import anthropic
from app.config import settings
from app.services.mock_functions import get_application_status, get_transaction_status

client = anthropic.Anthropic(api_key=settings.claude_api_key)
logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "get_application_status",
        "description": (
            "Look up the card application status for a customer. "
            "You MUST call this tool whenever a customer asks anything about their application, "
            "approval, card status, or whether their card has been issued. "
            "You do NOT have this information yourself — you must call this tool to get it. "
            "If the customer has not provided their customer ID, ask for it before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The customer's ID provided by the customer.",
                }
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_transaction_status",
        "description": (
            "Look up the status of a specific card transaction. "
            "You MUST call this tool whenever a customer reports a declined, failed, or stuck transaction, "
            "or asks why a payment did not go through. "
            "You do NOT have this information yourself — you must call this tool to get it. "
            "If the customer has not provided their transaction ID, ask for it before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID provided by the customer.",
                }
            },
            "required": ["transaction_id"],
        },
    },
]


def build_system_prompt(kb_content: str, additional_guidelines: str) -> str:
    prompt = f"You are a helpful customer service assistant for Atome, a Buy Now Pay Later service.\n\nKNOWLEDGE BASE:\n{kb_content}\n"
    if additional_guidelines.strip():
        prompt += f"\n{additional_guidelines}\n"
    return prompt


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_application_status":
        result = get_application_status(tool_input["customer_id"])
    elif tool_name == "get_transaction_status":
        result = get_transaction_status(tool_input["transaction_id"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    return json.dumps(result)


async def chat(
    messages: list[dict],
    kb_content: str,
    additional_guidelines: str,
) -> tuple[str, list[dict]]:
    """Send messages to Claude and return (assistant_text, tool_calls_used)."""
    system = build_system_prompt(kb_content, additional_guidelines)
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in messages[-20:]]
    tool_calls_used: list[dict] = []

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=claude_messages,
        )

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "I'm sorry, I couldn't process that request.")
            return text, tool_calls_used

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.warning("TOOL CALL >>> %s | input: %s", block.name, block.input)
                    result = process_tool_call(block.name, block.input)
                    logger.warning("TOOL RESULT >>> %s | output: %s", block.name, result)
                    tool_calls_used.append({"name": block.name, "input": block.input})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            claude_messages.append({"role": "assistant", "content": response.content})
            claude_messages.append({"role": "user", "content": tool_results})
            continue

        # Fallback
        text = next((b.text for b in response.content if hasattr(b, "text")), "I'm sorry, I couldn't process that request.")
        return text, tool_calls_used


async def suggest_fix(
    current_guidelines: str,
    customer_message: str,
    bot_response: str,
    complaint: str,
) -> str:
    """Ask Claude to suggest a fix to the guidelines based on a reported mistake."""
    prompt = f"""A customer reported that the bot gave an incorrect response. Analyze the mistake and suggest a concise addition or edit to the bot's guidelines to prevent this in the future.

CURRENT GUIDELINES:
{current_guidelines or "(none)"}

CUSTOMER MESSAGE:
{customer_message}

BOT RESPONSE:
{bot_response}

CUSTOMER COMPLAINT:
{complaint}

Respond with ONLY the updated guidelines text (the full new guidelines, not just the diff). Keep it concise."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def merge_guidelines(existing: str, fix: str) -> dict:
    """Detect conflicts between a fix and existing guidelines, return merge options."""
    if not existing or not existing.strip():
        return {"has_conflict": False, "merged": fix, "conflict_description": "",
                "override_version": fix, "keep_version": ""}

    prompt = f"""You are merging a bot behavior fix into existing guidelines.

EXISTING GUIDELINES:
{existing}

FIX TO INTEGRATE:
{fix}

Determine if the fix CONFLICTS with any part of the existing guidelines (directly contradicts or overrides it).

Respond ONLY with valid JSON:
{{
  "has_conflict": true or false,
  "conflict_description": "brief description of the conflict (empty string if none)",
  "merged": "full guidelines with fix cleanly integrated (when no conflict)",
  "override_version": "full guidelines where fix takes precedence over the conflicting part",
  "keep_version": "full guidelines keeping the existing instruction, fix is discarded"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


async def generate_bot_config(doc_content: str, manager_instructions: str) -> dict:
    """Meta-agent: generate bot config from a document and manager instructions."""
    prompt = f"""You are a bot configuration generator. Given a document and manager instructions, generate a customer service bot configuration.

DOCUMENT:
{doc_content[:8000]}

MANAGER INSTRUCTIONS:
{manager_instructions}

Respond with a JSON object with these fields:
- "kb_url": string (URL of the knowledge base, or empty string)
- "additional_guidelines": string (the system guidelines for the bot)
- "suggested_tools": list of strings (any special tools/functions the bot might need)

Respond ONLY with valid JSON."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
