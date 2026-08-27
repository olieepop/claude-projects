# 📬 Gmail Morning Brief

> **⚠️ Status: Portfolio / demo project — NOT my live pipeline.**
> My active morning brief runs in the cloud via Claude Cowork (`daily-inbox-briefing`,
> iMessage delivery) so it doesn't depend on my laptop being on. This repo is kept as a
> standalone code sample for my marketing-science portfolio. Not cron-scheduled.

A lightweight Python automation that fetches your Gmail inbox every morning,
summarizes it using Claude (Anthropic), and delivers a prioritized to-do brief
to your inbox at 7:30am — hands-free via cron.

Built as part of my [marketing-science-portfolio](https://github.com/olieepop/marketing-science-portfolio) tooling.

---

## What It Does

- Pulls all inbox threads from the last 24 hours (excluding promotions/social)
- Sends them to Claude Sonnet via the Anthropic API
- Returns a structured brief categorized by urgency:
  - 🔴 Urgent — act today
  - 🟡 This week
  - 🟢 FYI / no action
  - ⚠️ Flagged (recruiters, financial, unanswered threads)
- Emails the brief to your inbox, which hits your phone as a push notification

---

## Stack

| Tool | Purpose |
|---|---|
| Python 3.12+ | Runtime |
| Anthropic API (`claude-sonnet`) | Summarization |
| Gmail API (Google OAuth) | Read inbox + send email |
| `cron` | Daily scheduling (Mac/Linux) |

**Cost:** ~$0.01/day in Anthropic API usage. Everything else is free.

---

## Setup

### Prerequisites
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- A Google Cloud project with Gmail API enabled

### 1. Clone the repo

```bash
git clone https://github.com/olieepop/marketing-science-portfolio.git
cd marketing-science-portfolio/gmail-brief
```

### 2. Get Google API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable **Gmail API**
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON → rename it `credentials.json` → place in this folder

### 3. Run setup

```bash
bash setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Create a `.env` template
- Register the cron job at 7:30am PST

### 4. Add your API key

Edit `.env`:

```
ANTHROPIC_API_KEY=your_key_here
BRIEF_RECIPIENT_EMAIL=your@email.com
```

### 5. Authorize Gmail (first run only)

```bash
source .venv/bin/activate
python3 gmail_brief.py
```

A browser window will open asking you to authorize Gmail access. Do it once —
the token is saved locally and auto-refreshes forever after.

---

## Cron Schedule

The setup script registers this cron entry automatically:

```
30 15 * * * source /path/.env && /path/.venv/bin/python3 /path/gmail_brief.py >> /path/logs/gmail_brief.log 2>&1
```

`15:30 UTC = 7:30am PST`. Adjust for your timezone.

To verify it's registered:
```bash
crontab -l
```

---

## Security Notes

- `credentials.json`, `token.json`, and `.env` are all in `.gitignore` — they never get committed
- OAuth token is stored locally only
- The script only requests `gmail.modify` scope (read + send, no delete)

---

## Sample Output

```
📬 INBOX BRIEF — Thursday, May 07 2026

🔴 URGENT:
• Alex Coombes (Expedia) — Follow-up on case study submission, reply requested

🟡 THIS WEEK:
• Chase Bank — Statement available, review by May 10
• GitHub — Security advisory for a dependency in your repo

🟢 FYI:
• LinkedIn — 3 people viewed your profile
• Anthropic — API usage digest

⚠️ FLAGGED:
• Recruiter outreach from Meta (Data Science, Measurement) — no reply sent yet
```

---

## License

MIT
