# copilot-agent — GitHub Copilot / GitHub Models CLI Agent

Two CLI agents — choose the one that matches your setup:

## Quick Start

```bash
# 1. Authenticate (one-time)
gh extension install github/gh-copilot
gh auth login

# 2. Set up the virtual environment (one-time)
cd services/copilot-agent
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt

# 3a. Run the CLI agent
python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Hello"

# 3b. OR start the API server (for the Next.js UI)
python api_server.py             # http://localhost:8000
```


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
cd services/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

```
python agent_copilot.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream] [--max-turns N]
python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "Please provide the analysis of JIRA https://joeycmlam-1762529818344.atlassian.net/browse/SCRUM-9"
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

## api_server.py — REST API / SSE Mode

`api_server.py` exposes `AgentRunner` as a **FastAPI HTTP service**, supporting both a blocking JSON endpoint and a real-time Server-Sent Events (SSE) streaming endpoint. It reuses the same `AgentConfig`, `AgentRunner`, `BashTool`, and `WorkflowAnalyser` logic from `agent_copilot.py` unchanged.

### Setup

Requires the same virtual environment as `agent_copilot.py`. The extra dependencies (`fastapi`, `uvicorn`) are already included in `requirements.txt`.

```bash
cd services/copilot-agent
source .venv/bin/activate
pip install -r requirements.txt
```

### Starting the server

```bash
# Direct
python api_server.py

# With options
python api_server.py --host 127.0.0.1 --port 8000 --reload

# Via installed entry point (after pip install -e .)
agent-api --port 8000
```

The server starts on `http://0.0.0.0:8000` by default.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check → `{"status":"ok"}` |
| `GET` | `/agents` | List registered agents (id, name, description, skills, tools) + all `.md` files |
| `GET` | `/skills` | List registered skills (id, name, description) |
| `POST` | `/run` | Blocking run — waits for completion, returns `{"content":"..."}` |
| `POST` | `/stream` | SSE streaming — emits `data:` events in real time |

### Request body (`POST /run` and `POST /stream`)

```json
{
  "agent_file": "agents/assistant.md",
  "instruction": "Explain recursion",
  "model": "gpt-4o",
  "max_turns": 20,
  "extra_context": ""
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `agent_file` | yes | — | Relative path to an agent `.md` file |
| `instruction` | yes | — | The user prompt / task |
| `model` | no | `gpt-4o` | Any model available via the Copilot CLI |
| `max_turns` | no | `20` | Turn budget (capped at 50) |
| `extra_context` | no | `""` | Optional extra text prepended to the first message |

### SSE event types (`POST /stream`)

Each line is a `data: <JSON>\n\n` event:

| `type` | Payload | Description |
|--------|---------|-------------|
| `chunk` | `{"type":"chunk","content":"..."}` | Incremental assistant text delta |
| `tool` | `{"type":"tool","name":"..."}` | Tool invocation started (observability) |
| `done` | `{"type":"done","content":"..."}` | Final complete response; stream ends |
| `error` | `{"type":"error","message":"..."}` | Unhandled exception during the run |

### Examples

**Health check**
```bash
curl http://localhost:8000/health
```

**List agents**
```bash
curl http://localhost:8000/agents
```

**List skills**
```bash
curl http://localhost:8000/skills
```

**Blocking run**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'
```

**SSE streaming run** (chunks appear in real time)
```bash
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'
```

**BA workflow via API with extra context**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_file": "agents/ba.agent.md",
    "instruction": "please analyze the jira SCRUM-12",
    "model": "gpt-4o",
    "max_turns": 40
  }'
```

### Docker — API mode

The default `ENTRYPOINT` remains the CLI. To run as an API server:

```bash
docker run -p 8000:8000 <image> uvicorn api_server:app --host 0.0.0.0 --port 8000
```

---

## agent.py — GitHub Models Edition

Built on the **[azure-ai-inference](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-inference)** Python SDK. Authenticate with a GitHub personal access token to access any model on the GitHub Marketplace.

### Setup

```bash
cd services/copilot-agent
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

Agent files (`agents/*.agent.md`) are Markdown files with YAML frontmatter that define the **system prompt** and routing metadata used by the `AgentRegistry`.

### ATAF Frontmatter Schema

```yaml
---
id: my-agent              # unique ID used by the registry
name: "My Agent"          # human-readable display name
description: "..."        # shown in /agents; used for routing hints
triggers:                 # regex patterns matched against user input
  - "pattern one|variant"
  - "another pattern"
skills: [bdd-scenarios]   # skill IDs injected into context
tools: [read, search, edit, execute, agent]
argument-hint: "..."      # hint shown in the UI
---
```

### Bundled Agents

```
agents/
  assistant.md                  # General-purpose assistant
  coder.md                      # Software engineering focused
  jira-reader.md                # Reads and summarises Jira issues
  ba.agent.md                   # Business analyst — Jira analysis & requirements
  jira-test-automator.agent.md  # Generates automated tests from Jira stories
  test-designer.agent.md        # BDD test scenario design from requirements
  test-analyst.agent.md         # Test coverage analysis and mutation testing
  e2e-tester.md                 # Playwright end-to-end test authoring
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

## Skill Files

Skills (`skills/*.skill.md`) are reusable knowledge documents loaded by `SkillRegistry` at startup. Agents declare which skills they use via the `skills:` frontmatter key.

### ATAF Frontmatter Schema

```yaml
---
id: bdd-pytest            # unique ID referenced by agents
name: bdd-pytest          # human-readable name
description: "..."        # shown in /skills
argument-hint: "..."      # hint shown in the UI
---
```

### Bundled Skills

| ID | Description |
|----|-------------|
| `bdd-scenarios` | Gherkin scenario authoring guide |
| `bdd-pytest` | pytest-bdd feature files and step definitions |
| `bdd-playwright` | Playwright BDD with `playwright-bdd` |
| `bdd-cucumber-node` | Cucumber.js BDD for Node.js / TypeScript |
| `read-jira` | Fetching and analysing Jira issues via `jira-cli` |

Check registered skills at runtime:

```bash
curl http://localhost:8000/skills
```

---

## Packaging

The project uses `pyproject.toml` with `setuptools` as the build backend.

### Install as an editable package (development)

```bash
cd services/copilot-agent
pip install -e .
```

This registers three console entry points so you can run the agents from anywhere in your shell:

```bash
agent-copilot -a agents/assistant.md -m gpt-4o -i "Hello"   # → agent_copilot.py
agent-api --port 8000                                        # → api_server.py
```

### Build a distributable wheel

```bash
cd services/copilot-agent
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
| Entry point `agent-api` | `api_server:cli_main` (`api_server.py`) |
| Bundled modules | `agent`, `agent_copilot`, `api_server`, `registry` |
