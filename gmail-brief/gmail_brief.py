#!/usr/bin/env python3
"""
gmail_brief.py
--------------
Fetches the last 24 hours of Gmail inbox threads, summarizes them via
the Anthropic API, and sends the brief as an email to yourself.

Schedule with cron:
    30 7 * * * /usr/bin/python3 /path/to/gmail_brief.py >> /path/to/logs/gmail_brief.log 2>&1
"""

import os
import base64
import json
import datetime
import logging
from email.mime.text import MIMEText

import anthropic
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────

RECIPIENT_EMAIL   = os.environ.get("BRIEF_RECIPIENT_EMAIL", "oliviapan8@gmail.com")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SCOPES            = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH        = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_PATH  = os.path.join(os.path.dirname(__file__), "credentials.json")
MAX_THREADS       = 30   # threads to pull per run
MAX_SNIPPET_CHARS = 400  # chars per thread passed to Claude

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Gmail Auth ────────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

# ── Fetch Emails ──────────────────────────────────────────────────────────────

def fetch_recent_threads(service):
    """Pull inbox threads from the last 24 hours."""
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).strftime("%Y/%m/%d")
    query = f"in:inbox after:{since} -category:promotions -category:social"

    results = service.users().threads().list(
        userId="me",
        q=query,
        maxResults=MAX_THREADS,
    ).execute()

    threads = results.get("threads", [])
    log.info(f"Found {len(threads)} threads in the last 24h.")
    return threads

def extract_thread_summary(service, thread_id):
    """Get sender, subject, and snippet from a thread."""
    thread = service.users().threads().get(
        userId="me",
        id=thread_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ).execute()

    first_msg = thread["messages"][0]
    headers   = {h["name"]: h["value"] for h in first_msg["payload"]["headers"]}
    snippet   = first_msg.get("snippet", "")[:MAX_SNIPPET_CHARS]

    return {
        "from":    headers.get("From", "Unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date":    headers.get("Date", ""),
        "snippet": snippet,
        "unread":  "UNREAD" in first_msg.get("labelIds", []),
        "thread_count": len(thread["messages"]),
    }

# ── Claude Summarization ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Olivia's sharp, no-fluff personal email triage assistant.
Olivia is a senior analytics leader actively job searching. She cares most about:
recruiter/hiring manager emails, financial alerts, time-sensitive items, and anything
requiring a reply. She wants brutal clarity — no filler, no pleasantries."""

def build_user_prompt(threads_data, today_str):
    email_block = "\n\n".join([
        f"FROM: {t['from']}\nSUBJECT: {t['subject']}\nDATE: {t['date']}\n"
        f"UNREAD: {t['unread']} | THREAD_MSGS: {t['thread_count']}\nSNIPPET: {t['snippet']}"
        for t in threads_data
    ])

    return f"""Today is {today_str}. Here are Olivia's inbox threads from the last 24 hours.

{email_block}

---
Produce a tight inbox brief in this exact format:

📬 INBOX BRIEF — {today_str}

🔴 URGENT (respond or act TODAY):
• [Sender Name] — [1-line action needed]

🟡 THIS WEEK (act within 7 days):
• [Sender Name] — [1-line summary]

🟢 FYI / NO ACTION NEEDED:
• [Sender Name] — [1-line summary]

⚠️ FLAGGED:
• Any recruiter, hiring manager, or job-related emails
• Financial alerts or time-sensitive notifications  
• Threads needing a reply that haven't been answered

Rules:
- Under 350 words total
- If a category is empty, write "None."
- Be direct. No filler. No "I noticed that..." openers.
"""

def summarize_with_claude(threads_data):
    if not threads_data:
        return "📬 INBOX BRIEF\n\nNo new inbox emails in the last 24 hours. You're clear. ✅"

    client    = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today_str = datetime.datetime.now().strftime("%A, %B %d %Y")

    message = client.messages.create(
        model      = "claude-sonnet-4-20250514",
        max_tokens = 1000,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": build_user_prompt(threads_data, today_str)}],
    )

    return message.content[0].text

# ── Send Email ────────────────────────────────────────────────────────────────

def send_brief_email(service, brief_text):
    today_str = datetime.datetime.now().strftime("%b %d")
    subject   = f"☀️ Morning Brief — {today_str}"

    msg = MIMEText(brief_text, "plain")
    msg["To"]      = RECIPIENT_EMAIL
    msg["From"]    = "me"
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    log.info(f"Brief sent to {RECIPIENT_EMAIL} ✅")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting Gmail Brief run...")

    service      = get_gmail_service()
    raw_threads  = fetch_recent_threads(service)

    threads_data = []
    for t in raw_threads:
        try:
            threads_data.append(extract_thread_summary(service, t["id"]))
        except Exception as e:
            log.warning(f"Skipping thread {t['id']}: {e}")

    brief = summarize_with_claude(threads_data)
    log.info(f"\n{'='*60}\n{brief}\n{'='*60}")

    send_brief_email(service, brief)
    log.info("Done.")

if __name__ == "__main__":
    main()
