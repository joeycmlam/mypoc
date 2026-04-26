# mypoc — Full-Stack Monorepo

A full-stack monorepo for proof-of-concept (POC) projects, combining a **Next.js** frontend with independent **Python** backend services.

## Structure

```
mypoc/
├── app/               # Next.js App Router (pages, API routes, layouts)
├── components/        # React UI components
├── lib/               # Shared TypeScript utilities (utils.ts, types.ts, api.ts)
├── services/          # Python backend services (each service is self-contained)
│   ├── copilot-agent/ # FastAPI server + LLM agent runner
│   ├── jira-cli/      # Jira CLI tool for reading/writing tickets
│   └── pnl-engine/    # PnL engine service (BDD-tested)
├── docs/              # Architecture diagrams and design documents
└── .github/           # GitHub and workspace configuration
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | ≥ 18 | Next.js frontend |
| pnpm | ≥ 8 | Node package manager |
| Python | ≥ 3.9 | Python services |
| GitHub CLI (`gh`) | latest | Copilot agent auth |

---

## 1. Frontend — Next.js UI

The UI provides a chat interface that connects to the `copilot-agent` API server.

### Install dependencies

```bash
pnpm install
```

### Start development server

```bash
pnpm dev
```

The app is available at **http://localhost:3000**.

### Other commands

```bash
pnpm build    # Production build
pnpm start    # Start production server
pnpm lint     # Run ESLint
```

> The UI expects the `copilot-agent` API server to be running at `http://localhost:8000`. Start the backend service first (see below).

---

## 2. Backend Services

Each service under `services/` is fully independent with its own virtual environment and dependencies.

### copilot-agent (FastAPI + LLM Agent)

Full setup and usage instructions: [services/copilot-agent/README.md](services/copilot-agent/README.md)

**Quick start:**

```bash
cd services/copilot-agent

# One-time setup
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt

# Authenticate GitHub Copilot CLI (one-time)
gh extension install github/gh-copilot
gh auth login

# Start the API server
python api_server.py
```

Server runs at **http://localhost:8000**.

---

### jira-cli (Jira Issue Reader)

Full setup and usage instructions: [services/jira-cli/README.md](services/jira-cli/README.md)

**Quick start:**

```bash
cd services/jira-cli

# One-time setup
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt

# Configure credentials
cp .env.example .env               # then edit .env with your Jira URL, user, and API token

# Run
python jira_cli.py PROJECT-123
```

---

### pnl-engine (PnL Engine — in development)

Full details: [services/pnl-engine/](services/pnl-engine/)

BDD feature specs are under `services/pnl-engine/tests/features/`.

---

## Running the Full Stack

Open two terminals:

**Terminal 1 — Backend:**
```bash
cd services/copilot-agent
source .venv/bin/activate
python api_server.py
```

**Terminal 2 — Frontend:**
```bash
pnpm dev
```

Then open **http://localhost:3000** in your browser.

---

For more information, see [Copilot Instructions](.github/copilot-instructions.md)
