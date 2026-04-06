# copilot-agent — GitHub Copilot / GitHub Models CLI Agent

Two CLI agents — choose the one that matches your setup:

| Script | SDK | Auth |
|--------|-----|------|
| `agent_copilot.py` | `github-copilot-sdk` | GitHub Copilot CLI (OAuth) — **recommended** |
| `agent.py` | `azure-ai-inference` | `GITHUB_TOKEN` env var |

---

## agent_copilot.py — GitHub Copilot SDK Edition (Recommended)

Built on the **`github-copilot-sdk`** Python package, which delegates to the GitHub Copilot CLI running locally. No `GITHUB_TOKEN` is required — authentication is handled by the Copilot CLI's own credential store.

### Key Features

- **Two built-in tools** exposed to the model:
  - `bash_exec` — runs any shell command (async, 120 s timeout)
  - `invoke_agent` — delegates a sub-task to a specialised sub-agent (isolated session, own turn budget, depth-guarded)
- **`--max-turns`** flag — configurable turn budget (default 20, max 50), ideal for complex multi-step workflows
- **Async** throughout (`asyncio` / `async-await`)
- Access to any model available via the Copilot CLI (GPT-4o, Claude, etc.)

### Prerequisites

```bash
# Install the GitHub CLI and Copilot extension, then authenticate:
gh extension install github/gh-copilot
gh auth login
```

### Setup

```bash
cd app/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

```
python agent_copilot.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream] [--max-turns N]
```

#### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Agent Markdown/text file containing the system prompt |
| `-m`, `--model` | Model name available via Copilot CLI (default: `gpt-4o`) |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn chat session |
| `--no-stream` | Disable streaming; wait for the full response |
| `--max-turns N` | Max turns per run (default: 20, max: 50). Increase for complex workflows |

### Examples

**Single-shot**
```bash
python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**BA workflow with extended turn budget**
```bash
python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "please analyze the jira SCRUM-12" --max-turns 40
```

**Pipe from stdin**
```bash
cat main.py | python agent_copilot.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent_copilot.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive
```

**Different models**
```bash
python agent_copilot.py -a agents/assistant.md -m claude-sonnet-4-6 -i "Hello"
python agent_copilot.py -a agents/assistant.md -m gpt-4o-mini -i "Hello"
```

### Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |

---

## agent.py — GitHub Models Edition

Built on the **[azure-ai-inference](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-inference)** Python SDK. Authenticate with a GitHub personal access token to access any model on the GitHub Marketplace.

### Setup

```bash
cd app/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your GitHub token as an environment variable:

```bash
export GITHUB_TOKEN="github_pat_..."
```

> Create a token at <https://github.com/settings/tokens> — only **`models:read`** scope is needed.

### Usage

```
python agent.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream]
```

#### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Agent Markdown/text file containing the system prompt |
| `-m`, `--model` | Model name from [github.com/marketplace/models](https://github.com/marketplace/models) (default: `gpt-4o`) |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn chat session |
| `--no-stream` | Disable streaming; wait for the full response |

### Examples

**Single-shot**
```bash
python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**Pipe from stdin**
```bash
cat main.py | python agent.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent.py -a agents/coder.md -m gpt-4o --interactive
```

**Different models** (any name from the GitHub Marketplace):
```bash
python agent.py -a agents/assistant.md -m mistral-large -i "Hello"
python agent.py -a agents/assistant.md -m meta-llama-3.1-70b-instruct -i "Hello"
python agent.py -a agents/assistant.md -m Phi-3.5-MoE-instruct -i "Hello"
```

### Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `reset` | Clear conversation history (keeps system prompt) |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |

### Available Models (GitHub Marketplace)

Browse all available models at <https://github.com/marketplace/models>.  
Notable ones include:

| Model | Provider |
|-------|----------|
| `gpt-4o` | OpenAI |
| `gpt-4o-mini` | OpenAI |
| `mistral-large` | Mistral |
| `meta-llama-3.1-70b-instruct` | Meta |
| `Phi-3.5-MoE-instruct` | Microsoft |
| `AI21-Jamba-1.5-Large` | AI21 Labs |

---

## Agent Files

Agent files are plain text or Markdown files that become the **system prompt**.

```
agents/
  assistant.md                  # General-purpose assistant
  coder.md                      # Software engineering focused
  ba.agent.md                   # Business analyst — Jira analysis & requirements
  jira-reader.md                # Reads and summarises Jira issues
  jira-test-automator.agent.md  # Generates automated tests from Jira stories
  playwright-tester.agent.md    # Playwright end-to-end test authoring
  test-designer.md              # Test plan and test case design
```

Create your own for any persona or task:

```markdown
# agents/data_scientist.md
You are a senior data scientist. Respond with concise Python code using
pandas and matplotlib. Explain each step briefly.
```

Then run:
```bash
python agent_copilot.py -a agents/data_scientist.md -m gpt-4o -i "Plot a sine wave"
```

---

## Packaging

The project uses `pyproject.toml` with `setuptools` as the build backend.

### Install as an editable package (development)

```bash
cd app/copilot-agent
pip install -e .
```

This registers two console entry points so you can run the agents from anywhere in your shell:

```bash
agent-copilot -a agents/assistant.md -m gpt-4o -i "Hello"   # → agent_copilot.py
```

### Build a distributable wheel

```bash
cd app/copilot-agent
pip install build
python -m build
```

Outputs are placed in `dist/`:

```
dist/
  copilot_agent-1.0.0-py3-none-any.whl
  copilot_agent-1.0.0.tar.gz
```

### Install from the wheel

```bash
pip install dist/copilot_agent-1.0.0-py3-none-any.whl
```

### pyproject.toml overview

| Setting | Value |
|---------|-------|
| Build backend | `setuptools` |
| Package name | `copilot-agent` |
| Version | `1.0.0` |
| Python requirement | `>=3.9` |
| Entry point `copilot-agent` | `agent:main` (`agent.py`) |
| Entry point `agent-copilot` | `agent_copilot:main` (`agent_copilot.py`) |
| Bundled modules | `agent`, `agent_copilot` |
