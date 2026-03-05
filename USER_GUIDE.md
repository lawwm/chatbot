# Atome Bot Platform — User Guide

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Dashboard](#dashboard)
4. [Creating a Bot](#creating-a-bot)
5. [Bot Settings](#bot-settings)
6. [Knowledge Base](#knowledge-base)
7. [Mistakes & Auto-Fix](#mistakes--auto-fix)
8. [Roles & Permissions](#roles--permissions)
9. [Customer Chat](#customer-chat)
10. [Metabot](#metabot)

---

## Overview

The Atome Bot Platform lets you create and manage AI-powered customer service bots. There are two sides to the platform:

- **Customer Chat** — A public chat interface where customers talk to your bot. No login required.
- **Manager Dashboard** — An authenticated area where managers create bots, manage knowledge bases, review mistakes, and control access.

---

## Getting Started

1. Go to `/auth/login` and log in with your credentials.
2. You will be redirected to the **Dashboard**, which lists all bots you have access to.
3. If no bots exist yet, click **New Bot** to create your first one.

---

## Dashboard

The dashboard (`/dashboard`) shows all bots you have created or been assigned a role on.

Each bot card displays:
- Bot name and public URL (`/chat/{slug}`)
- Quick links to **Settings**, **Mistakes**, and **Roles**

**Creator accounts** can see all bots and access all features. Regular users only see bots they have been assigned a role on.

---

## Creating a Bot

Go to **Dashboard → New Bot** (`/dashboard/bots/new`).

| Field | Description |
|---|---|
| **Bot Name** | The display name for your bot |
| **Knowledge Base URLs** | One or more URLs to scrape for help content. Click **+ Add URL** to add more. |
| **Additional Guidelines** | Instructions injected into the bot's system prompt — tone, rules, tool-use instructions, etc. |
| **Public** | If checked, anyone with the chat link can use the bot. If unchecked, only assigned users can access it. |
| **Enable Auto-Fix** | When a customer reports a mistake, the AI automatically suggests and applies a guideline fix. |
| **Allow Override on Conflict** | If auto-fix finds a conflict with existing guidelines, apply it anyway. If unchecked, conflicts are held for manual review. |

### Advanced Scraper Settings

Expand the **Advanced Scraper Settings** section to fine-tune how the knowledge base is built:

| Setting | Default | Notes |
|---|---|---|
| Max articles | 30 | Maximum pages scraped per seed URL |
| Crawl depth | 1 | How many link-hops to follow from the seed URL |
| Strategy | BFS | BFS = broad coverage; DFS = follow one path deeply |
| Request delay | 500ms | Pause between requests (be polite to servers) |
| Request timeout | 20s | How long to wait for a page to load |
| Max chars per article | 3000 | Characters kept per page |

Click **Create Bot** to save. If you added a KB URL, scraping starts automatically.

---

## Bot Settings

Go to **Dashboard → (Bot) → Settings** (`/dashboard/bots/{id}/settings`).

### Saving Changes

Edit any field and click **Save Settings**. Changes to the knowledge base URL will trigger a re-scrape automatically.

To re-scrape without changing any settings, click **Repopulate Knowledge Base**.

### Writing Guidelines

The **Additional Guidelines** field supports Markdown. Use the **Edit / Preview** tabs above the text area to switch between writing and previewing your formatting.

Good guidelines are clear and imperative. Example:

```
You help customers with questions about the Atome Card.

TOOL USE RULES:
- If a customer asks about their application status: you MUST call get_application_status.
  Ask for their customer ID first if not provided.
- If a customer reports a failed transaction: you MUST call get_transaction_status.
  Ask for their transaction ID first if not provided.

GENERAL RULES:
- Answer only from the knowledge base.
- Be concise, friendly, and professional.
- If the answer is not in the knowledge base, say so honestly.
```

---

## Knowledge Base

The knowledge base is built by scraping one or more URLs. The bot uses this content to answer customer questions.

### Scraping Progress

When a scrape is running, a live progress bar appears at the bottom of the settings page showing:
- Current URL being visited (colour-coded: yellow = visiting, green = scraped, red = failed)
- Article count (`X scraped · Y visited`)
- A **Done** badge when complete

All buttons are disabled during scraping to prevent conflicts.

### How the Bot Uses the KB

When a customer sends a message, the platform:
1. Searches the KB for the most relevant chunks using vector similarity
2. Injects those chunks into the bot's context
3. Falls back to the full KB text only if no relevant chunks are found

---

## Mistakes & Auto-Fix

Go to **Dashboard → (Bot) → Mistakes** (`/dashboard/bots/{id}/mistakes`).

Customers can report incorrect bot responses directly from the chat interface. Each report becomes a **Mistake** entry for managers to review.

### Reviewing a Mistake

Each open mistake shows:
- **Customer said** — the original message
- **Bot responded** — what the bot said
- **Customer complaint** — why it was wrong

### Fixing a Mistake

Click **Analyze & Suggest Fix**. The AI will:
1. Analyse the mistake
2. Suggest an updated version of the guidelines to prevent it in future
3. Check for conflicts with the existing guidelines

**No conflict:** An editable text area appears with the suggested fix. Edit if needed, then click **Apply Fix & Archive**.

**Conflict detected:** Two options are shown side by side:
- **Use Existing** — keep the current guidelines, discard this fix
- **Apply Fix** — override the conflicting guideline with the new fix

### Auto-Fix

If **Enable Auto-Fix** is turned on for the bot, the platform automatically analyzes reported mistakes and applies fixes without requiring manual intervention. Conflicts are held for review unless **Allow Override on Conflict** is also enabled.

### Archive

The last 20 applied fixes are shown in the **Archive** section at the bottom of the page. Click any row in the **Fix Applied** column to view the full guidelines text that was saved.

---

## Roles & Permissions

Go to **Dashboard → (Bot) → Roles** (`/dashboard/bots/{id}/roles`).

Roles let you grant specific users access to specific features of a bot.

### Permissions

| Permission | What it grants |
|---|---|
| `VIEW_SETTINGS` | View the bot's settings page |
| `EDIT_KB_URL` | Add or change knowledge base URLs |
| `EDIT_GUIDELINES` | Edit the additional guidelines |
| `TOGGLE_AUTOFIX` | Enable or disable auto-fix |
| `REVIEW_MISTAKES` | View and analyze customer-reported mistakes |
| `APPROVE_FIXES` | Apply or dismiss a fix for a reported mistake |
| `MANAGE_ROLES` | Create, delete, assign, and revoke roles |
| `DELETE_BOT` | Delete the bot entirely |

### Creating a Role

1. Enter a **Role Name** (e.g. "Support Agent")
2. Check the permissions you want to grant
3. Click **Create Role**

### Assigning a Role

Under the role card, enter a **username** and click **Assign**. The user will immediately gain that role's permissions on this bot.

### Revoking a Role

Click **Revoke** next to a user's name under any role card to remove their assignment.

### Deleting a Role

Click **Delete Role** on a role card. This permanently removes the role and revokes all assignments for that role.

---

## Customer Chat

Customers access the bot at `/chat/{bot-slug}` — no login required.

### Sending Messages

- Type in the input box and press **Enter** to send
- Press **Shift + Enter** for a new line
- The bot responds with formatted text, tables, and lists where appropriate

### Tool Calls

Some questions trigger live data lookups:
- **Application status** — the bot calls `get_application_status`. It will ask for your Customer ID first if you haven't provided it.
- **Transaction status** — the bot calls `get_transaction_status`. It will ask for your Transaction ID first.

When a tool is called, a small indicator appears above the bot's response showing which tool was used.

### Reporting a Mistake

If the bot gives an incorrect or unhelpful response, click **Report mistake** below the response bubble. Fill in why the response was wrong and submit. A manager will review it.

---

## Metabot

Go to **Metabot** in the top navigation (`/meta`). Available to creator accounts only.

The Metabot is an AI assistant that lets you manage the entire platform through natural conversation — no need to navigate the dashboard manually.

### What You Can Ask

| Task | Example |
|---|---|
| List bots | "Show me all my bots" |
| View settings | "What are the settings for TrustBot?" |
| Update guidelines | "Update TrustBot's guidelines to always respond in English" |
| Change KB URL | "Set the KB URL for TrustBot to https://help.example.com" |
| Scrape KB | "Repopulate the knowledge base for TrustBot" |
| Review mistakes | "Show me open mistakes for TrustBot" |
| Analyze a mistake | "Analyze mistake #3 for TrustBot" |
| Apply a fix | "Apply the suggested fix for that mistake" |
| Create a bot | "Create a new bot called SupportBot" |
| Delete a bot | "Delete the NUS Manager bot" |
| Manage roles | "Create a reviewer role for TrustBot with REVIEW_MISTAKES and APPROVE_FIXES" |
| Assign a role | "Assign the reviewer role to alice" |

### Scraping Progress

When the Metabot triggers a knowledge base scrape, a live progress panel appears just above the input box showing real-time scraping status. Click **✕** to dismiss it once the scrape is complete.

### Conversations

- Each session is saved as a separate conversation in the left sidebar
- Click **New chat** to start a fresh conversation
- Click a conversation title to rename it (inline edit)
- Click **✕** on a conversation to delete it

---

*For technical issues, contact your platform administrator.*
