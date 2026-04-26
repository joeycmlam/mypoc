# pnl-engine — Portfolio P&L Engine

A Python service that calculates **realised** and **unrealised** Profit & Loss for portfolio positions using the Weighted Average Cost (WAC) method. Jobs are scheduled via **APScheduler** and run weekly (Sunday night) to ensure Monday-morning figures are always current.

## Overview

| Feature | Description |
|---------|-------------|
| Realised P/L | Calculated for closed/partially-closed positions using WAC |
| Unrealised P/L | Calculated for open positions against current market prices |
| Batch scheduler | APScheduler cron jobs — price sync, unrealised P/L, realised P/L |
| UI trigger | On-demand realised P/L calculation via UI |

## Project Structure

```
pnl-engine/
├── src/
│   └── pnl_engine/       # Service source code
├── tests/
│   ├── features/         # BDD feature specs (Gherkin)
│   │   ├── realised_pnl.feature
│   │   ├── unrealised_pnl.feature
│   │   ├── scheduler_batch.feature
│   │   └── ui_realised_pnl_trigger.feature
│   └── step_defs/        # pytest-bdd step definitions
└── docs/
    └── adr/              # Architecture Decision Records
```

## Quick Start

```bash
# 1. Set up the virtual environment (one-time)
cd services/pnl-engine
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt  # once requirements.txt is added

# 2. Run tests
pytest tests/
```

## Scheduled Jobs

Three APScheduler cron jobs are registered at service startup:

| Job ID | Schedule (UTC) | Description |
|--------|---------------|-------------|
| `price_fetch_sync` | Sun 21:00 | Fetch prices and sync to DB |
| `unrealised_pnl_engine` | Sun 22:00 | Unrealised P/L engine (WAC) |
| `realised_pnl_engine` | Sun 22:00 | Realised P/L engine (WAC) |

## BDD Feature Specs

Behaviour-driven scenarios are written in Gherkin and located in `tests/features/`:

- `realised_pnl.feature` — Scheduled and on-demand realised P/L calculation
- `unrealised_pnl.feature` — Unrealised P/L for open positions
- `scheduler_batch.feature` — APScheduler Sunday-night batch job registration and execution
- `ui_realised_pnl_trigger.feature` — UI-triggered on-demand P/L calculation

> This service is currently in development. Source code and step definitions are in progress.
