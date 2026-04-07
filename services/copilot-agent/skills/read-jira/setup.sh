#!/usr/bin/env bash
# setup.sh — First-time setup for jira-cli
# Run from the repo root: bash .github/skills/read-jira/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="$(cd "$SCRIPT_DIR/../../../../jira-cli" && pwd)"

echo "==> Setting up jira-cli at: $CLI_DIR"

# 1. Create virtual environment if it doesn't exist
if [ ! -d "$CLI_DIR/.venv" ]; then
  echo "==> Creating virtual environment..."
  python3 -m venv "$CLI_DIR/.venv"
else
  echo "==> Virtual environment already exists, skipping."
fi

# 2. Install dependencies
echo "==> Installing dependencies..."
"$CLI_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$CLI_DIR/.venv/bin/pip" install --quiet -r "$CLI_DIR/requirements.txt"

# 3. Create .env from .env.example if not already present
if [ ! -f "$CLI_DIR/.env" ]; then
  cp "$CLI_DIR/.env.example" "$CLI_DIR/.env"
  echo ""
  echo "==> Created $CLI_DIR/.env from .env.example"
  echo "    Fill in your Jira credentials:"
  echo ""
  echo "    JIRA_URL        — e.g. https://yourorg.atlassian.net"
  echo "    JIRA_USER       — your Jira account email"
  echo "    JIRA_API_TOKEN  — create at https://id.atlassian.com/manage-profile/security/api-tokens"
  echo ""
else
  echo "==> .env already exists, skipping."
fi

echo ""
echo "==> Setup complete!"
echo ""
echo "    Activate:  source $CLI_DIR/.venv/bin/activate"
echo "    Run:       python $CLI_DIR/jira_cli.py PROJECT-123"
echo "    Pipe:      python $CLI_DIR/jira_cli.py PROJECT-123 | python services/copilot-agent/agent.py -a services/copilot-agent/agents/jira-reader.md -m gpt-4o"
