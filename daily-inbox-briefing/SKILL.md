---
name: daily-inbox-briefing
description: 7am daily inbox triage — extract action items, send iMessage summary, log to-dos to Notion My Tasks
---

Good morning! It's 7am. Run Olivia's daily inbox briefing.

## Step 1 — Fetch unread emails
Use `mcp__1d0d66d0-7296-45ba-a0ac-2a859f072c0d__search_threads` with:
- query: `is:unread in:inbox -in:draft newer_than:1d`
- pageSize: 50

## Step 2 — Extract action items
For each thread, review sender, subject, and snippet. Classify as:
- **Urgent**: Needs reply or action TODAY (deadlines, appointments, government/legal, time-sensitive)
- **Normal**: Handle within a few days
- **FYI only**: Newsletters, promos, auto-confirmations — skip entirely

Write each action as a short specific imperative, e.g. "Prepare for Dragontree appointment Mon May 11".

## Step 3 — Send iMessage summary to +18478685687
Use `mcp__Read_and_Send_iMessages__send_imessage` to send a concise briefing. Keep under 300 words, phone-readable.

**If there are no unread emails or zero action items, send exactly this and nothing else:**
```
☀️ Inbox clear — nothing needs you today
```

Otherwise format as:
```
☀️ Morning Briefing — [Today's Date]

📬 [N] unread • [N] action items

⚡ URGENT
• [Item]

📋 TODO
• [Item]

🗓️ TODAY
• [Appointments or deadlines]
```

Only include sections that have items.

## Step 4 — Write action items to Notion My Tasks
Use `mcp__9690c2f3-451b-4415-95e9-904e55777bd3__notion-create-pages` to add each urgent/normal action item as a task.

- parent: `{ "type": "database_id", "database_id": "5e732088-e408-4545-9fec-31a6dab56f08" }`
- For each item, set:
  - `"Task name"`: the action item text
  - `"Due"`: today's date in ISO format (YYYY-MM-DD)
  - `"Status"`: `"To-do"`
  - `"Source"`: `"Inbox Briefing"`

Create all items in a single call using the `pages` array. Skip FYI-only items.

## Step 5 — Log completion
Output a brief summary: emails processed, action items found, iMessage confirmed sent, Notion tasks created (list task names).
