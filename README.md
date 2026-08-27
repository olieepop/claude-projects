# Daily Inbox Briefing

> **Retired — Aug 2026.** Claude Cowork now has a native daily briefing built in, so I stopped running this custom version. Leaving the code and docs here in case the Notion + iMessage routing is useful to someone (or future me). Full comparison below if you're deciding which one to use.

## Why I retired it

Cowork's built-in briefing does the core job — pull your morning context, prioritize it, hand you a summary — without me maintaining connector IDs and a SKILL.md by hand. It's just less specific than what I'd wired up.

| | This custom build | Cowork's native briefing |
|---|---|---|
| Sources | Gmail only | Gmail, Calendar, Slack, Sentry, web, local files |
| Delivery | iMessage text + Notion to-dos | Cowork window, or email/Slack |
| Setup | Connect 3 MCP servers, edit SKILL.md by hand, build a Notion database | Connect once, point a scheduled task at it — a few minutes |
| Where it runs | Needs a scheduled agent session | Runs on Anthropic's servers, no machine required |
| Tuning | Fully custom — classification rules, message format, all editable | Handles the reasoning for you, less to tweak |
| Cost | Free (your own connectors) | Included in Claude Pro / Cowork |

If you specifically want the iMessage-to-phone + Notion-logging workflow, this repo still does that and the native version doesn't (yet). That's the one reason I'd come back to it.

---

This is another test to leverage AI to automate some recurring daily admin work. I leveraged Claude Cowork's scheduled task that runs every morning at 7am to triage my Gmail inbox, send a concise iMessage summary to my phone, and log action items directly into a Notion database — no manual effort required.

I initially wanted to only apps within my phone (e.g. Reminders to-dos) but you will need to grant the permission while your laptop is awake (?). If you came across this repo and have answer, please let me know bc moving it to Notion somehow is not as clean as how I want it. But for any of you don't mind using Notion or has been a power user, feel free to leverage below process to make your life easier. 

Next step, I wanted to see if I can upload my writing style to allow Cladue to reply some emails for me. Totally inspired by a reel I came across the other day that a guy created a process to automate his text to his girlfriend who went on a solo Bali trip for two weeks. Instead of doing moring/evening greeting + asking how she was doing, he downloaded their chat and make AI automatically respond to her text. LOL. Inspiring idea but guys, please don't generalize it, okay. LOL 

## What it does

1. **Fetches** up to 50 unread emails from your Gmail inbox
2. **Classifies** each thread as Urgent, Normal, or FYI (skipped)
3. **Sends** a formatted iMessage briefing to your phone
4. **Creates** Notion to-do entries for every action item, tagged by priority and due date
5. **Logs** a completion summary in the session

## Prerequisites

You'll need the following connectors installed and authenticated in Claude Cowork:

| Connector | Purpose |
|---|---|
| Gmail | Read unread inbox threads |
| iMessage (Read and Send) | Send morning briefing to your phone |
| Notion | Create to-do entries |

## Setup

### 1. Install connectors
In Cowork, go to **Settings → Connectors** and connect Gmail, iMessage, and Notion.

### 2. Find your MCP IDs
Each connector is assigned a unique ID when installed. To find yours, ask Claude:
> "What are the MCP tool names available for Gmail and Notion?"

Your Gmail MCP ID will look like: `mcp__xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx__search_threads`

### 3. Create the Notion database
In your Notion workspace, create a database called **To-dos** with these properties:

| Property | Type | Options |
|---|---|---|
| Task | Title | — |
| Status | Select | To Do (red), Done (green) |
| Priority | Select | Urgent (red), Normal (yellow) |
| Due Date | Date | — |
| Source | Text | — |

Note the database ID from the URL: `https://notion.so/YOUR_DATABASE_ID`

### 4. Configure SKILL.md
Open `SKILL.md` and replace the following placeholders:

| Placeholder | Replace with |
|---|---|
| `YOUR_GMAIL_MCP_ID` | Your Gmail connector MCP ID |
| `YOUR_EMAIL@gmail.com` | Your Gmail address |
| `YOUR_PHONE_NUMBER` | Your phone number (digits only, e.g. `14155550123`) |
| `YOUR_NOTION_MCP_ID` | Your Notion connector MCP ID |
| `YOUR_NOTION_DATABASE_ID` | Your Notion To-dos database ID |

### 5. Install the scheduled task
In Claude Cowork, create a new scheduled task pointing to this `SKILL.md` and set it to run daily at 7am (or your preferred time).

## Customization

- **Run time**: Change the schedule to any time that suits your morning routine
- **Email volume**: Adjust `pageSize` in Step 1 (max 50)
- **Classification rules**: Edit the criteria in Step 2 to match what's urgent for you
- **Message format**: Modify the iMessage template in Step 3
- **Multiple Gmail accounts**: Connect additional Gmail connectors and add a second `search_threads` call in Step 1, merging results before classification

## License

MIT
