#!/bin/bash
# setup.sh — One-time setup for gmail-brief
# Run once: bash setup.sh

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  gmail-brief setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"

# ── 1. Create virtual environment ────────────────────────────────────────────
echo "▶ Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ── 2. Install dependencies ───────────────────────────────────────────────────
echo "▶ Installing dependencies..."
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "  Dependencies installed ✅"

# ── 3. Create logs directory ──────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
echo "▶ Logs directory: $LOG_DIR ✅"

# ── 4. Check for .env ─────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "⚠️  No .env file found. Creating template..."
    cat > "$SCRIPT_DIR/.env" << 'EOF'
ANTHROPIC_API_KEY=your_anthropic_api_key_here
BRIEF_RECIPIENT_EMAIL=oliviapan8@gmail.com
EOF
    echo "  → Edit .env and add your ANTHROPIC_API_KEY before running."
fi

# ── 5. Check for credentials.json ────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/credentials.json" ]; then
    echo ""
    echo "⚠️  credentials.json not found."
    echo "  → Download it from Google Cloud Console and place it here:"
    echo "  → $SCRIPT_DIR/credentials.json"
fi

# ── 6. Register cron job (7:30am PST = 15:30 UTC) ────────────────────────────
echo ""
echo "▶ Registering cron job for 7:30am PST daily..."

CRON_CMD="30 15 * * * source $SCRIPT_DIR/.env && $VENV_DIR/bin/python3 $SCRIPT_DIR/gmail_brief.py >> $LOG_DIR/gmail_brief.log 2>&1"

# Check if cron already exists
(crontab -l 2>/dev/null | grep -q "gmail_brief.py") && {
    echo "  Cron job already registered. Skipping."
} || {
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "  Cron job registered ✅"
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Add ANTHROPIC_API_KEY to .env"
echo "  2. Place credentials.json in this folder"
echo "  3. Run: source .venv/bin/activate && python3 gmail_brief.py"
echo "     (First run opens a browser to authorize Gmail access)"
echo "  4. After auth works once, cron handles everything daily."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
