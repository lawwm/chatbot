# Atome Customer Service Bot Platform

**Live demo:** https://chatbot-production-4f99.up.railway.app/

**Documentation:** [User Guide](./USER_GUIDE.md) · [Technical Guide](./TECHNICAL_GUIDE.md)

---

## Table of Contents

- [Part 1 — Customer Service Bot](#part-1--customer-service-bot)
  - [1. Knowledge Base Q&A](#1-knowledge-base-qa)
  - [2. Application Status Tool Call](#2-application-status-tool-call)
  - [3. Failed Transaction Tool Call](#3-failed-transaction-tool-call)
  - [4. Editing the Knowledge Base URL](#4-editing-the-knowledge-base-url)
  - [5. Editing Additional Guidelines](#5-editing-additional-guidelines)
  - [6. Reporting a Mistake](#6-reporting-a-mistake)
  - [7. Reviewing a Mistake in the Dashboard](#7-reviewing-a-mistake-in-the-dashboard)
  - [8. Auto-Fix & Mistake Archive](#8-auto-fix--mistake-archive)
- [Part 2 — Meta-Agent Bot Builder](#part-2--meta-agent-bot-builder)
  - [9. Opening the Metabot](#9-opening-the-metabot)
  - [10. Creating a Bot via Conversation](#10-creating-a-bot-via-conversation)
  - [11. Triggering Knowledge Base Scraping](#11-triggering-knowledge-base-scraping)
  - [12. Updating Bot Settings via Conversation](#12-updating-bot-settings-via-conversation)
  - [13. Reviewing and Fixing Mistakes via Metabot](#13-reviewing-and-fixing-mistakes-via-metabot)
- [Additional Features](#additional-features)
  - [14. Authentication](#14-authentication)
  - [15. Roles & Granular Permissions](#15-roles--granular-permissions)
  - [16. Multi-Bot Dashboard](#16-multi-bot-dashboard)
  - [17. Public vs Private Bots](#17-public-vs-private-bots)
- [Details](#details)
  - [Metabot Tool Call Verification](#metabot-tool-call-verification)
  - [Conflict Detection and the Override Checkbox](#conflict-detection-and-the-override-checkbox)
- [Technical Overview](#technical-overview)
  - [Tools and Technologies](#tools--technologies)
  - [Development Tools](#development-tools)
  - [Architecture](#architecture)

---

## Part 1 — Customer Service Bot

### 1. Knowledge Base Q&A

The bot is seeded with the Atome Card help center (`https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card`). When a customer asks a question that is covered by the knowledge base, the bot retrieves the relevant content using vector search and answers accurately.

**Steps:**
1. Go to [App](https://chatbot-production-4f99.up.railway.app/) — no login required.
2. Click into Atome Bot. 
3. Type a question about the Atome Card (e.g. *"What is the Atome Card?"* or *"What is a Temporary Limit?"*).
4. The bot responds using content scraped from the help center.

<!-- SCREENSHOT: Customer chat showing a knowledge base question and bot response -->
<img width="1781" height="559" alt="image" src="https://github.com/user-attachments/assets/1ceff7f8-2d15-4c25-86d3-75d7abe1fd8f" />
<img width="1684" height="723" alt="image" src="https://github.com/user-attachments/assets/d4b07989-e1b7-4e4f-a023-b6c6fc338daa" />
---

### 2. Application Status Tool Call

When a customer asks about their card application status, the bot calls a backend function (`get_application_status`) to retrieve live status data — it does not guess or hallucinate.

**Steps:**
1. In the customer chat, ask: *"What is my application status?"*
2. The bot asks for your Customer ID if not already provided.
3. Provide a Customer ID (e.g. `C001`).
4. A **blue pill** appears above the bot's response confirming that `get_application_status` was called.
5. The bot reports the application status returned by the function.

<!-- SCREENSHOT: Chat showing the blue "get application status" pill and the bot's status response -->
<img width="1660" height="868" alt="image" src="https://github.com/user-attachments/assets/88c7fd59-b0e2-477c-934f-d8627f858258" />

---

### 3. Failed Transaction Tool Call

When a customer reports a failed or declined transaction, the bot calls `get_transaction_status` to look up the real status — it does not guess.

**Steps:**
1. In the customer chat, ask: *"My transaction failed, can you help?"*
2. The bot asks for your Transaction ID.
3. Provide a Transaction ID (e.g. `T001`).
4. A **blue pill** appears confirming that `get_transaction_status` was called.
5. The bot reports the transaction status.

<!-- SCREENSHOT: Chat showing the blue "get transaction status" pill and the bot's response -->
<img width="1671" height="859" alt="image" src="https://github.com/user-attachments/assets/45fa48c6-4894-433e-b2c0-4a68ef1f4d7f" />

---

### 4. Editing the Knowledge Base URL

Managers can change the URL the bot scrapes for knowledge base content. The bot immediately re-scrapes and updates its answers accordingly.

**Steps:**
1. Log in and go to **Dashboard → (Bot) → Settings**.
2. Update the **Knowledge Base URL** field with a new URL.
3. Click **Save Settings** to modify and change web scraping settings.
4. Click **Repopulate Knowledge Base** to initiate web scraping.
5. A live scraping progress bar appears at the bottom of the page, showing each URL being visited (yellow = visiting, green = scraped, red = failed).
6. Once complete, the bot uses the new knowledge base for all future conversations.

<!-- SCREENSHOT: Settings page showing the KB URL field and the live scrape progress bar -->
<img width="1665" height="837" alt="image" src="https://github.com/user-attachments/assets/06419b14-e48a-480a-b3b8-265c2707ddfc" />
<img width="1766" height="727" alt="image" src="https://github.com/user-attachments/assets/2ce90aab-e0a7-465d-91fa-021d6a9851fc" />
<img width="1312" height="861" alt="image" src="https://github.com/user-attachments/assets/09faa7f5-96c1-4cfb-907f-2cf157983aa2" />

---

### 5. Editing Additional Guidelines

Managers can write custom instructions (tone, tool-use rules, restricted topics) that are injected directly into the bot's system prompt. Changes take effect immediately.

**Steps:**
1. On the **Settings** page, scroll to **Additional Guidelines**.
2. Use the **Edit / Preview** tabs to write and preview Markdown-formatted instructions.
3. Click **Save Settings**.
4. Return to the customer chat — the bot now follows the updated instructions.

<!-- SCREENSHOT: Settings page showing the guidelines editor with Edit/Preview tabs -->
<img width="829" height="597" alt="image" src="https://github.com/user-attachments/assets/f016d583-5923-42d8-8f08-0e6936722943" />

---

### 6. Reporting a Mistake

Customers can flag incorrect bot responses directly from the chat interface — no login required.

**Steps:**
1. In the customer chat, find a response that is wrong or unhelpful.
2. Click **Report mistake** below the bot's response bubble.
3. A modal appears. Describe what was wrong in the complaint field.
4. Click **Submit**.
5. A success banner confirms the report was received.

<!-- SCREENSHOT: Chat interface showing the "Report mistake" button and the modal with the complaint field -->
<img width="884" height="638" alt="image" src="https://github.com/user-attachments/assets/d52a76d2-af86-4446-90da-d43cf029ef4c" />
<img width="976" height="723" alt="image" src="https://github.com/user-attachments/assets/286fee0a-0491-47ce-a451-6ed235ec19c7" />

---

### 7. Reviewing a Mistake in the Dashboard

Every reported mistake is visible to managers in the dashboard, showing the full context: what the customer asked, what the bot said, and what the complaint was.

**Steps:**
1. Log in and go to **Dashboard → (Bot) → Mistakes**.
2. Each open mistake card shows:
   - **Customer said** — the original message
   - **Bot responded** — the incorrect response
   - **Customer complaint** — why it was wrong
3. Click **Analyze & Suggest Fix** to have the AI propose a guideline correction.
4. If no conflict is detected, an editable text area appears with the suggested fix.
5. Edit if needed, then click **Apply Fix & Archive**.

<!-- SCREENSHOT: Mistakes page showing an open mistake card with "Analyze & Suggest Fix" button -->
<img width="1238" height="498" alt="image" src="https://github.com/user-attachments/assets/c31babf2-5a55-4e5b-b167-3d2b5647125f" />

<!-- SCREENSHOT: Mistakes page showing the suggested fix text area and "Apply Fix & Archive" button -->
<img width="1231" height="770" alt="image" src="https://github.com/user-attachments/assets/b837a169-4c2e-40b3-be8e-3f02c3efb390" />
<img width="1172" height="798" alt="image" src="https://github.com/user-attachments/assets/b52dd748-e772-46b9-b418-9fe59307d940" />

---

### 8. Auto-Fix & Mistake Archive

When **Auto-Fix** is enabled on a bot, mistakes are automatically analyzed and the guidelines are updated the moment a customer submits a report — no manual review needed. Every applied fix is archived for audit.

**Steps to verify auto-fix:**
1. Ensure **Enable Auto-Fix** and **Allow Override on Conflict** are both checked in the bot's Settings.
2. Submit a mistake report from the customer chat.
3. Wait a few seconds for the background task to complete.
4. Go to **Dashboard → (Bot) → Settings** — the **Additional Guidelines** field will have been updated automatically.
5. Go to **Dashboard → (Bot) → Mistakes** — the mistake is gone from the open list.
6. Scroll down to the **Archive** section — the fix is logged with the timestamp and the full guidelines text that was applied.

<!-- SCREENSHOT: Mistakes page Archive section showing a row with the fix that was applied -->
<img width="458" height="237" alt="image" src="https://github.com/user-attachments/assets/3095614c-0ab4-43c2-8b8f-6d7469ca9218" />


<!-- SCREENSHOT: Bot settings page showing updated guidelines after auto-fix was applied -->
<img width="1267" height="561" alt="image" src="https://github.com/user-attachments/assets/104914ed-4e7a-4587-acee-b07d3f9559ad" />

<img width="1203" height="870" alt="image" src="https://github.com/user-attachments/assets/3b5b95cc-59b5-435e-ab70-dcaa5fb561a5" />

---

## Part 2 — Meta-Agent Bot Builder

### 9. Opening the Metabot

The Metabot is a conversational AI assistant for managers. Instead of clicking through forms, managers can describe what they want and the Metabot takes action on their behalf.

**Steps:**
1. Log in with a **creator account**.
2. Click **Metabot** in the top navigation bar.
3. A chat interface opens. Each conversation is saved in the left sidebar.
4. Click **New chat** to start a fresh session.

<!-- SCREENSHOT: Metabot page showing the chat interface and conversation sidebar -->
<img width="1901" height="873" alt="image" src="https://github.com/user-attachments/assets/098cbc09-0c33-4318-8da3-b616bcc6d01c" />

---

### 10. Creating a Bot via Conversation

Managers can create a fully configured bot just by describing it in plain language.

**Steps:**
1. In the Metabot, type: *"Create a new bot called SupportBot for the Atome Card help center."*
2. The Metabot calls the `create_bot` tool (a **blue pill** appears confirming the tool call).
3. The Metabot confirms creation and provides the bot's chat link and ID.
4. The new bot immediately appears in the dashboard.

<!-- SCREENSHOT: Metabot chat showing the tool pill and the bot creation confirmation message -->
<img width="1876" height="866" alt="image" src="https://github.com/user-attachments/assets/4cef1ef5-3164-460a-b03b-400a0e6c30b6" />


<!-- SCREENSHOT: Dashboard showing the newly created bot card -->
<img width="1442" height="686" alt="image" src="https://github.com/user-attachments/assets/3b2883ab-ffab-4991-bb82-aab00f3386fd" />

---

### 11. Triggering Knowledge Base Scraping

After creating a bot, managers can tell the Metabot to populate the knowledge base by providing a URL.

**Steps:**
1. In the Metabot, type: *"Scrape the knowledge base for SupportBot using https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card"*
2. The Metabot calls the `trigger_scrape` tool.
3. A **live scraping panel** appears just above the chat input, showing real-time progress (current URL, articles scraped vs visited, colour-coded status).
4. When complete, the panel shows a green **Done** badge.
5. Click **✕** to dismiss the panel.

<!-- SCREENSHOT: Metabot chat showing the live scraping progress panel with URL status and article count -->
<img width="1093" height="698" alt="image" src="https://github.com/user-attachments/assets/d5140856-b5be-46da-9afb-28da052db9fb" />
<img width="1887" height="868" alt="image" src="https://github.com/user-attachments/assets/e9a9bdb5-6d99-4993-8f47-ed72010c9697" />

---

### 12. Updating Bot Settings via Conversation

Managers can update any bot setting — guidelines, KB URL, auto-fix toggles — through natural language without touching the dashboard.

**Steps:**
1. In the Metabot, type: *"Update SupportBot's guidelines to always respond in English and never discuss pricing."*
2. The Metabot calls `get_bot_settings` then `update_bot_settings` (blue pills appear for each tool call).
3. The Metabot confirms the change.
4. Navigate to **Dashboard → SupportBot → Settings** — the guidelines field reflects the update.

<!-- SCREENSHOT: Metabot chat showing two tool pills (get_bot_settings, update_bot_settings) and the confirmation message -->
<img width="1876" height="869" alt="image" src="https://github.com/user-attachments/assets/74e47d3d-b8cb-4ed2-a516-7de25853c638" />
<img width="1876" height="869" alt="image" src="https://github.com/user-attachments/assets/29099b65-f5ea-479a-b9a7-19f28a1552b4" />

<!-- SCREENSHOT: Bot settings page showing the updated guidelines -->
<img width="1476" height="736" alt="image" src="https://github.com/user-attachments/assets/0b71d8ca-1ff5-4ee7-842b-34a822ee54a9" />

---

### 13. Reviewing and Fixing Mistakes via Metabot

Managers can review, analyze, and fix reported mistakes entirely through the Metabot — no dashboard navigation required.

**Steps:**
1. In the Metabot, type: *"Show me open mistakes for SupportBot."*
2. The Metabot calls `list_mistakes` and displays each mistake with its ID, customer message, bot response, and complaint.
3. Type: *"Analyze mistake #1 for SupportBot."*
4. The Metabot calls `analyze_mistake`, then returns the suggested fix.
5. Type: *"Apply the suggested fix."*
6. The Metabot calls `apply_fix`, updates the guidelines, and archives the mistake.
7. The fix is now live — the bot's behavior is updated for all future conversations.

<!-- SCREENSHOT: Metabot listing open mistakes with IDs and complaint summaries -->
<img width="870" height="584" alt="image" src="https://github.com/user-attachments/assets/fc25679c-cfdd-4bda-92fd-378121379227" />

<!-- SCREENSHOT: Metabot showing the suggested fix after analyzing a mistake -->
<img width="761" height="809" alt="image" src="https://github.com/user-attachments/assets/7218a245-af4a-424b-bda2-517ee4b98e83" />

<!-- SCREENSHOT: Metabot confirming the fix was applied and the mistake archived -->
<img width="779" height="632" alt="image" src="https://github.com/user-attachments/assets/9d3ec1ec-e4aa-48ae-a813-9979705bd6d7" />
<img width="1139" height="206" alt="image" src="https://github.com/user-attachments/assets/d2b023c6-cd60-4595-b144-60655f6b8b94" />

---

## Additional Features

### 14. Authentication

The dashboard is fully protected by server-side session authentication. Customers access the chat with no login required; only managers need credentials.

**Logging in:**
1. Go to `/auth/login`.
2. Enter your username and password.
3. On success you are redirected to the **Dashboard**.
4. A session cookie is set (HTTPOnly, server-side session stored in MongoDB with a configurable TTL).



**Logging out:**
1. Click **Logout** in the top navigation bar.
2. The session is invalidated and the cookie is cleared immediately.

**Access control:**
- Unauthenticated users trying to reach `/dashboard` or any protected route are redirected to `/auth/login`.
- Customer chat at `/chat/{slug}` is always public — no login required.

<!-- SCREENSHOT: Login page -->
<img width="1178" height="615" alt="image" src="https://github.com/user-attachments/assets/6e1b9630-fbd2-46d8-928a-e94cdece8097" />

<!-- SCREENSHOT: Dashboard after login showing the user's bots -->
<img width="1262" height="565" alt="image" src="https://github.com/user-attachments/assets/48ae0744-c048-47f6-9a1b-29a719640ea6" />

---

### 15. Roles & Granular Permissions

Each bot has its own role system. A creator can define named roles with any combination of the eight available permissions, then assign those roles to specific users. This lets you give a support agent access to review mistakes without letting them delete the bot or change guidelines.

**Available permissions:**

| Permission | What it grants |
|---|---|
| `VIEW_SETTINGS` | View the bot's settings page |
| `EDIT_KB_URL` | Add or change knowledge base URLs |
| `EDIT_GUIDELINES` | Edit additional guidelines |
| `TOGGLE_AUTOFIX` | Enable or disable auto-fix |
| `REVIEW_MISTAKES` | View and analyze reported mistakes |
| `APPROVE_FIXES` | Apply or dismiss a suggested fix |
| `MANAGE_ROLES` | Create, delete, assign, and revoke roles |
| `DELETE_BOT` | Delete the bot entirely |

**Creating a role:**
1. Go to **Dashboard → (Bot) → Roles**.
2. Enter a role name (e.g. *"Support Agent"*).
3. Check the permissions to grant.
4. Click **Create Role**.

<!-- SCREENSHOT: Roles page showing the role creation form with permission checkboxes -->
<img width="1146" height="89" alt="image" src="https://github.com/user-attachments/assets/b5a8ddb6-c85e-495f-8434-b99b8bc7400f" />
<img width="1017" height="659" alt="image" src="https://github.com/user-attachments/assets/55b72559-bd0d-45df-aa87-40e796f63feb" />
<img width="975" height="776" alt="image" src="https://github.com/user-attachments/assets/3881d0ec-dba6-4320-953f-8fd89fbe59a6" />

**Assigning a role to a user:**
1. Under the role card, enter a username.
2. Click **Assign**.
3. The user immediately gains those permissions on this bot.

<!-- SCREENSHOT: Role card showing an assigned user with a Revoke button -->
<img width="1073" height="727" alt="image" src="https://github.com/user-attachments/assets/e0323145-c142-4c92-b7c6-19f708efb242" />
<img width="999" height="473" alt="image" src="https://github.com/user-attachments/assets/1215ba23-7b6f-47f8-b303-bda0ad8f0790" />

**Revoking and deleting:**
- Click **Revoke** next to a username to remove their assignment.
- Click **Delete Role** to permanently remove the role and all its assignments.

<!-- SCREENSHOT: Roles page showing multiple roles with assigned users -->
<img width="1092" height="165" alt="image" src="https://github.com/user-attachments/assets/bcf62434-8f60-43b7-b6cc-7a86c2568a8d" />

---

### 16. Multi-Bot Dashboard

The platform supports any number of bots. The dashboard gives a bird's-eye view of every bot you own or have been assigned a role on.

**Steps:**
1. Log in and go to `/dashboard`.
2. Each bot card shows the bot name and its public chat link (`/chat/{slug}`).
3. Quick links — **Settings**, **Mistakes**, **Roles** — appear on each card for bots you have access to manage.
4. Click **New Bot** to create another bot. Each bot has its own independent knowledge base, guidelines, role assignments, and mistake history.

<!-- SCREENSHOT: Dashboard showing multiple bot cards with their quick-action links -->
<img width="920" height="380" alt="image" src="https://github.com/user-attachments/assets/146f4392-630a-4140-b7d7-2f4064d4ae02" />
<img width="952" height="621" alt="image" src="https://github.com/user-attachments/assets/0cb53031-0fed-4648-9ab9-c15009c86e04" />

---

### 17. Public vs Private Bots

Each bot can be set to **public** (anyone with the link can chat) or **private** (only users with an assigned role can access the chat).

**Setting visibility:**
1. Go to **Dashboard → (Bot) → Settings**.
2. Toggle the **Public** checkbox.
3. Click **Save Settings**.

**Effect:**
- **Public on:** `/chat/{slug}` is accessible to anyone without logging in.
- **Public off:** Unauthenticated visitors to `/chat/{slug}` are turned away. Only users who have been assigned a role on that bot (and are logged in) can access the chat.

<!-- SCREENSHOT: Settings page showing the Public toggle checkbox -->
<img width="953" height="709" alt="image" src="https://github.com/user-attachments/assets/21d77159-6fbe-4961-a484-590e3fee1cd5" />
<img width="931" height="293" alt="image" src="https://github.com/user-attachments/assets/40dda02c-9a8e-40b1-b493-4676e6f94e4c" />

---

### Details

#### Metabot Tool Call Verification

Sometimes the Metabot hallucinates web scraping — it may describe the action without actually performing it. The blue pill indicator is the ground truth: it only appears when the tool was genuinely called. If you don't see the pill, the action did not happen. Keep prompting the Metabot until the pill confirms it ran.

<img width="1883" height="931" alt="image" src="https://github.com/user-attachments/assets/a648fdd1-ccbc-4610-a548-8abdcd03a9a0" />

---

#### Conflict Detection and the Override Checkbox

**Why this exists**

When a customer reports a mistake, the AI suggests a fix by rewriting the bot's guidelines. But the existing guidelines may already contain an instruction that directly contradicts the new fix — for example, the current guidelines say *"always respond formally"* and the suggested fix says *"respond casually for billing questions"*. Blindly overwriting would silently break an existing rule the manager deliberately set.

To prevent this, every suggested fix is checked against the current guidelines before being applied. If a contradiction is found, the system flags it as a **conflict** and gives the manager a choice rather than applying the fix automatically.

**The two settings that control this (in Bot Settings):**

| Setting | Behaviour |
|---|---|
| **Enable Auto-Fix** | When a customer reports a mistake, the AI automatically analyzes it and attempts to apply a fix without any manager action. |
| **Allow Override on Conflict** | If a conflict is detected during auto-fix, apply the new fix anyway (override the conflicting rule). If unchecked, conflicts are held for manual review instead. |

<!-- SCREENSHOT: Settings page showing the Enable Auto-Fix and Allow Override on Conflict checkboxes -->
<img width="330" height="165" alt="image" src="https://github.com/user-attachments/assets/cc9d3085-0b6c-47d6-a36c-952eeb71badf" />

**Manual review flow (when auto-fix is off, or conflict is held):**

1. Go to **Dashboard → (Bot) → Mistakes**.
2. Click **Analyze & Suggest Fix** on an open mistake.
3. The AI analyzes the mistake and checks for conflicts with the current guidelines.

**No conflict:** A single editable text area appears with the fully merged guidelines. Edit if needed, then click **Apply Fix & Archive**.

<!-- SCREENSHOT: Mistakes page showing the no-conflict suggested fix text area -->

**Conflict detected:** Two options are shown side by side — the manager chooses which version of the guidelines to keep:

- **Use Existing** — keep the current guidelines as-is; the suggested fix is discarded.
- **Apply Fix** — the new fix takes precedence; the conflicting existing rule is overridden.

<!-- SCREENSHOT: Mistakes page showing the conflict view with "Use Existing" and "Apply Fix" side by side -->
<img width="1001" height="586" alt="image" src="https://github.com/user-attachments/assets/67723941-927e-4238-849b-7669c6c57e06" />

---

## Technical Overview

### Tools & Technologies

| Category | Tool |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **Frontend** | Jinja2 (server-side rendering), HTMX, DaisyUI, Tailwind CSS |
| **Database** | MongoDB Atlas (Motor async driver) |
| **AI / LLM** | Anthropic Claude API (Haiku for chat & auto-fix, Sonnet for meta-agent) |
| **Embeddings** | Voyage AI (`voyage-3-lite`, 512 dimensions) |
| **Vector Search** | MongoDB Atlas Vector Search |
| **Web Scraping** | BeautifulSoup4, httpx |
| **Auth** | Server-side sessions, passlib (bcrypt), HTTPOnly cookies |
| **Hosting** | Railway |

---

### Development Tools

This project was built using:

- **[Claude Code](https://claude.ai/code)** with **Claude Sonnet 4.6** (primary coding agent) and **Claude Opus** (architecture planning and complex reasoning)
- **ChatGPT** with **GPT-5.2** (secondary reference and alternative perspectives during design)
- **Visual Studio Code** (editor)

---

### Architecture

**Request flow:** The client sends an HTTP request → FastAPI routes it → a service function queries MongoDB or calls the Claude API → a Jinja2 template is rendered server-side and returned as HTML. HTMX handles partial page updates by swapping targeted HTML fragments, avoiding full page reloads without a JS framework.

**Server-side rendering:** All pages are Jinja2 templates rendered on the server. HTMX posts forms and receives HTML partials in response, which it inserts into the DOM. This keeps the frontend simple — no React, no build step, no state management.

**MongoDB:** Three logical areas of data — bot configuration (`bots`), user/auth data (`users`, `sessions`, `roles`, `user_roles`), and runtime data (`conversations`, `mistakes`, `mistakes_archive`, `kb_content`, `kb_vectors`). Indexes on `slug`, `session_id`, and `username` enforce uniqueness; a TTL index on `sessions.expires_at` automatically purges expired sessions.

**Claude integration:** Chat uses `claude-haiku-4-5` for low-latency responses. The meta-agent and auto-fix pipeline also use Haiku. The model is called in a tool-use loop — if the model returns `stop_reason: tool_use`, the server executes the requested function and feeds the result back, repeating until `stop_reason: end_turn`. The tool_use response contains the name of the function, and the server uses it to execute a function from a function table.

**Vector indexing:** When a URL is scraped, each article is split into chunks and embedded using Voyage AI's `voyage-3-lite` model, producing a 512-dimensional dense vector per chunk. These vectors are stored in the `kb_vectors` collection in MongoDB Atlas alongside the source text and `bot_id`. A MongoDB Atlas Vector Search index (`vector_index`) is defined over the `embedding` field using cosine similarity. At query time, the customer's message is embedded with the same Voyage model, and a `$vectorSearch` aggregation pipeline retrieves the top-10 most semantically similar chunks filtered by `bot_id`. This means the bot finds relevant content by meaning, not keyword match — a customer asking *"why was I charged twice?"* will surface articles about duplicate transactions even if those exact words never appear in the knowledge base. If vector search returns no results (e.g. the knowledge base hasn't been scraped yet), the system falls back to injecting the full raw article text into the context.

