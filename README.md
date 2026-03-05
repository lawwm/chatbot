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

---

## Part 1 — Customer Service Bot

### 1. Knowledge Base Q&A

The bot is seeded with the Atome Card help center (`https://help.atome.ph/hc/en-gb/categories/4439682039065-Atome-Card`). When a customer asks a question that is covered by the knowledge base, the bot retrieves the relevant content using vector search and answers accurately.

**Steps:**
1. Go to `/chat/{bot-slug}` — no login required.
2. Type a question about the Atome Card (e.g. *"What is the Atome Card?"* or *"How do I activate my card?"*).
3. The bot responds using content scraped from the help center.

<!-- SCREENSHOT: Customer chat showing a knowledge base question and bot response -->

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

---

### 4. Editing the Knowledge Base URL

Managers can change the URL the bot scrapes for knowledge base content. The bot immediately re-scrapes and updates its answers accordingly.

**Steps:**
1. Log in and go to **Dashboard → (Bot) → Settings**.
2. Update the **Knowledge Base URL** field with a new URL.
3. Click **Save Settings**.
4. A live scraping progress bar appears at the bottom of the page, showing each URL being visited (yellow = visiting, green = scraped, red = failed).
5. Once complete, the bot uses the new knowledge base for all future conversations.

<!-- SCREENSHOT: Settings page showing the KB URL field and the live scrape progress bar -->

---

### 5. Editing Additional Guidelines

Managers can write custom instructions (tone, tool-use rules, restricted topics) that are injected directly into the bot's system prompt. Changes take effect immediately.

**Steps:**
1. On the **Settings** page, scroll to **Additional Guidelines**.
2. Use the **Edit / Preview** tabs to write and preview Markdown-formatted instructions.
3. Click **Save Settings**.
4. Return to the customer chat — the bot now follows the updated instructions.

<!-- SCREENSHOT: Settings page showing the guidelines editor with Edit/Preview tabs -->

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

<!-- SCREENSHOT: Mistakes page showing the suggested fix text area and "Apply Fix & Archive" button -->

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

<!-- SCREENSHOT: Bot settings page showing updated guidelines after auto-fix was applied -->

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

---

### 10. Creating a Bot via Conversation

Managers can create a fully configured bot just by describing it in plain language.

**Steps:**
1. In the Metabot, type: *"Create a new bot called SupportBot for the Atome Card help center."*
2. The Metabot calls the `create_bot` tool (a **blue pill** appears confirming the tool call).
3. The Metabot confirms creation and provides the bot's chat link and ID.
4. The new bot immediately appears in the dashboard.

<!-- SCREENSHOT: Metabot chat showing the tool pill and the bot creation confirmation message -->

<!-- SCREENSHOT: Dashboard showing the newly created bot card -->

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

---

### 12. Updating Bot Settings via Conversation

Managers can update any bot setting — guidelines, KB URL, auto-fix toggles — through natural language without touching the dashboard.

**Steps:**
1. In the Metabot, type: *"Update SupportBot's guidelines to always respond in English and never discuss pricing."*
2. The Metabot calls `get_bot_settings` then `update_bot_settings` (blue pills appear for each tool call).
3. The Metabot confirms the change.
4. Navigate to **Dashboard → SupportBot → Settings** — the guidelines field reflects the update.

<!-- SCREENSHOT: Metabot chat showing two tool pills (get_bot_settings, update_bot_settings) and the confirmation message -->

<!-- SCREENSHOT: Bot settings page showing the updated guidelines -->

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

<!-- SCREENSHOT: Metabot showing the suggested fix after analyzing a mistake -->

<!-- SCREENSHOT: Metabot confirming the fix was applied and the mistake archived -->


## Use MetaBot to create a bot via conversation:

<img width="1896" height="941" alt="Screenshot 2026-03-06 001620" src="https://github.com/user-attachments/assets/f32e370a-16db-414f-a6c6-791cd7cd5bc4" />

### -> Tell the MetaBot how you want to create the Bot.

<img width="1898" height="938" alt="Screenshot 2026-03-06 001628" src="https://github.com/user-attachments/assets/c8e82fb4-c0a9-4efb-bf85-aad7e5993a58" />

### -> The MetaBot will create and display the information for you, as well as guide you through Bot creation!

<img width="1891" height="935" alt="Screenshot 2026-03-06 001639" src="https://github.com/user-attachments/assets/5f1f2a51-8838-4ada-9ea3-9b757c99908d" />

### -> Blue pills will appear on the top left of chat conversations to tell you that an actual function has been called.

<img width="1802" height="630" alt="Screenshot 2026-03-06 001652" src="https://github.com/user-attachments/assets/db982c86-adca-480a-af80-fab914ed0963" />

### -> You can edit settings of the bot as well!

<img width="1877" height="932" alt="Screenshot 2026-03-06 001702" src="https://github.com/user-attachments/assets/cd121c77-2f9e-4b0b-9012-8a62e42a9ea0" />

### -> You can also trigger web scraping using the knowledge base URL.

<img width="1858" height="935" alt="Screenshot 2026-03-06 001712" src="https://github.com/user-attachments/assets/29ff59aa-fb66-40a6-9d82-bc2d045d95d2" />

### -> Sometimes the agent hallucinates web scraping, but the blue pill for tooling will only appear if web scraping did actually happen.

<img width="1883" height="931" alt="image" src="https://github.com/user-attachments/assets/a648fdd1-ccbc-4610-a548-8abdcd03a9a0" />

### -> You can keep prompting the MetaBot until you are sure it actually did start the web scraping.