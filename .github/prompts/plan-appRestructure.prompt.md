# Plan: Restructure `app/` Directory

**TL;DR** — Move all three Python sub-projects out of the Next.js `app/` directory (which is reserved for App Router), into a new top-level `services/` directory. Simultaneously create the missing `lib/` directory that is currently crashing the frontend build.

---

## Problems

| # | Issue | Impact |
|---|-------|--------|
| 1 | Python projects (`copilot-agent`, `jira-cli`) live inside Next.js's `app/` | Namespace conflict with App Router; deployment ambiguity |
| 2 | `lib/` directory missing entirely | Frontend **won't build** — 10+ components import `@/lib/utils`, `@/lib/api`, `@/lib/types` |
| 3 | `app/copilot-agent/build/` and `copilot_agent.egg-info/` committed to repo | Noisy, shouldn't be tracked |
| 4 | Hardcoded paths in Python scripts and agent `.md` files reference `app/jira-cli/...`, `app/copilot-agent/...` | Will break after the move |

---

## Target Structure

```
mypoc/
├── app/                    ← Next.js App Router only (unchanged content)
│   ├── layout.tsx, page.tsx, globals.css
│   └── api/agents|health|run|stream/
├── lib/                    ← CREATE (missing)
│   ├── utils.ts            # cn() — clsx + tailwind-merge
│   ├── types.ts            # Message, ConnectionStatus, StreamEvent
│   └── api.ts              # fetchAgents, checkHealth, streamAgent, getAgentDisplayName, getAgentDescription
├── components/             ← unchanged
├── services/               ← NEW top-level dir
│   ├── copilot-agent/      ← MOVED from app/copilot-agent/
│   └── jira-cli/           ← MOVED from app/jira-cli/
└── docs/
```

---

## Steps

### Phase 1 — Relocate Python projects (steps 1–3 parallel)

1. Move `app/copilot-agent/` → `services/copilot-agent/`
2. Move `app/jira-cli/` → `services/jira-cli/`

### Phase 2 — Fix path references (depends on Phase 1)

4. `agent.py` line 32 and `agent_copilot.py` line 49: both load `.env` from `_here.parent / "jira-cli" / ".env"`. After move, `_here.parent` = `services/` and `jira-cli` is still a sibling — **no code change needed** ✓
5. `xrun.sh`: update paths (assumes `app/` as CWD) → run from within `services/copilot-agent/`
6. `ba.agent.md` lines 48, 173, 182: `python jira-cli/jira_cli.py` — update to `python ../jira-cli/jira_cli.py` (needs confirming `bash_exec` CWD in `api_server.py`)
7. `setup.sh` in `.github/skills/read-jira/`: `app/jira-cli` hardcoded path → update to `services/jira-cli`
8. `SKILL.md` in `.github/skills/read-jira/`: all example commands referencing `app/jira-cli/` and `app/copilot-agent/` → update to `services/`
9. `jira-test-automator.agent.md`: relative links like `../../../app/copilot-agent/agents/...` → update to correct relative paths from `services/copilot-agent/agents/`
10. `test-analyst.agent.md`: references `app/` working directory convention → update

### Phase 3 — Create missing `lib/` directory (parallel with Phase 1–2)

11. Create `lib/utils.ts` — `cn()` function wrapping `clsx` + `tailwind-merge`
12. Create `lib/types.ts` — infer `Message`, `ConnectionStatus`, `StreamEvent` interfaces from component usage
13. Create `lib/api.ts` — `fetchAgents()`, `checkHealth()`, `streamAgent()` (SSE client), `getAgentDisplayName()`, `getAgentDescription()` — infer signatures from `agent-chat.tsx`, `agent-selector.tsx`, `sidebar.tsx`

### Phase 4 — Cleanup (depends on Phase 1)

14. Add `services/copilot-agent/build/` and `**/*.egg-info/` to `.gitignore`
15. Update `copilot-instructions.md` to document the new `services/` tier

---

## Relevant Files

- `app/copilot-agent/agent.py` — `.env` load path (line 32)
- `app/copilot-agent/agent_copilot.py` — `.env` load path (line 49)
- `app/copilot-agent/xrun.sh` — run-script paths
- `app/copilot-agent/agents/ba.agent.md` — `jira-cli` command paths (lines 48, 173, 182)
- `app/copilot-agent/.github/skills/read-jira/setup.sh` — hardcoded `app/jira-cli` path
- `app/copilot-agent/.github/skills/read-jira/SKILL.md` — documented command examples
- `app/copilot-agent/agents/jira-test-automator.agent.md` — agent file relative links
- `app/copilot-agent/agents/test-analyst.agent.md` — `app/` working directory references
- `components/agent-chat.tsx` — consumer of missing lib/ functions

---

## Verification

1. `pnpm build` succeeds (TypeScript compiles, no missing `lib/` module errors)
2. `pnpm dev` loads UI — agent list populates, health check passes, model selector works
3. `cd services/copilot-agent && python api_server.py` — FastAPI server starts on `:8000`
4. `cd services/copilot-agent && python agent.py --help` — loads `.env` from `../jira-cli/.env` correctly
5. BA agent workflow: check that `bash_exec` resolves `jira-cli/jira_cli.py` from the new CWD

---

## Decisions

- `lib/` → **create as part of this task**
- `packages/` directory → **not needed** (json-validator removed)
- Python projects naming convention → **`services/`** for backend services

## Open Question

Before updating `ba.agent.md`'s `python jira-cli/jira_cli.py` commands, verify what working directory `bash_exec` uses at runtime in `api_server.py` — it could be the project root, `services/`, or `services/copilot-agent/`, and the correct relative path differs in each case.
