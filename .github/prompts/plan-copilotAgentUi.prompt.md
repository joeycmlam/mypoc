## Plan: Next.js Chat UI for Copilot Agent API

**TL;DR** — Build a Next.js 14 (App Router + TypeScript + Tailwind CSS) web app in a new `app/copilot-agent-ui/` sub-project. It connects to the existing FastAPI backend (`api_server.py`) via SSE streaming (`POST /stream`) and provides a full agent chat interface with conversation history, tool-call observability, and per-run controls.

---

### Phase 1 — Project Scaffolding

1. Create `app/copilot-agent-ui/` with `package.json`, `tsconfig.json`, `next.config.ts`, `tailwind.config.ts`, `postcss.config.js`
2. Install dependencies: `next`, `react`, `react-dom`, `typescript`, `tailwindcss`, `postcss`, `autoprefixer`, `react-markdown`, `remark-gfm`

### Phase 2 — Shared Types & API Layer

3. `src/lib/types.ts` — `Message`, `Conversation`, `RunRequest`, `AgentEvent`, `AppConfig` TypeScript types
4. `src/lib/api.ts` — typed wrappers: `fetchHealth()`, `fetchAgents()`, `runAgent()`, `streamAgent()`
5. `src/lib/sse.ts` — POST SSE helper using `fetch()` + `ReadableStream` (required because `EventSource` only supports GET, but `/stream` is `POST`)

### Phase 3 — State Hooks

6. `src/hooks/useConversation.ts` — conversation CRUD, message append, `localStorage` persistence across reloads
7. `src/hooks/useAgentStream.ts` — wraps `streamAgent()`, handles `chunk` / `tool` / `done` / `error` SSE events, exposes `isStreaming` + `abort()`

### Phase 4 — Components *(parallel within phase)*

8. `AgentControls.tsx` — agent file dropdown (populated from `GET /agents`), model selector (hardcoded list), max-turns slider
9. `ToolCallBadge.tsx` — inline pill showing the active tool name (`bash_exec`, `invoke_agent`, etc.)
10. `MessageBubble.tsx` — renders user/assistant messages with `react-markdown` + streaming cursor animation
11. `MessageList.tsx` — scrollable container, auto-scrolls to bottom as chunks arrive
12. `InputBar.tsx` — resizable textarea, Send button (disabled while streaming), Ctrl+Enter submit, Stop button to abort
13. `Sidebar.tsx` + `ConversationItem.tsx` — left panel: list sessions, new/select/delete conversation
14. `ChatPanel.tsx` — composes `MessageList` + `InputBar`, wires `useAgentStream`

### Phase 5 — Pages & Layout

15. `src/app/layout.tsx` — root HTML shell, Tailwind base, Inter font
16. `src/app/chat/page.tsx` — two-column layout: `<Sidebar>` + `<ChatPanel>` with `<AgentControls>` in the top bar
17. `src/app/page.tsx` — `redirect('/chat')`

### Phase 6 — Documentation

18. `app/copilot-agent-ui/README.md` — setup instructions, `NEXT_PUBLIC_API_URL` env var, how to run both services together

---

### Relevant Files

| File | Role |
|------|------|
| `app/copilot-agent/api_server.py` | Backend — provides `/agents`, `/run`, `/stream` endpoints consumed by the UI |
| `app/copilot-agent/agent_copilot.py` | Agent logic — `AgentConfig`, `AgentRunner`, SSE event types reused for documentation |
| `app/copilot-agent-ui/src/lib/sse.ts` | Critical: POST-based SSE via `fetch()` + `ReadableStream` |
| `app/copilot-agent-ui/src/hooks/useAgentStream.ts` | Core streaming state machine |

---

### API Endpoints Consumed

| Method | Path | Used for |
|--------|------|----------|
| `GET` | `/health` | Backend connectivity check on startup |
| `GET` | `/agents` | Populate agent selector dropdown |
| `POST` | `/stream` | Real-time SSE streaming (primary mode) |
| `POST` | `/run` | Fallback blocking mode |

### SSE Event Types (from `/stream`)

| `type` | Payload | UI handling |
|--------|---------|-------------|
| `chunk` | `{"type":"chunk","content":"..."}` | Append text to assistant bubble |
| `tool` | `{"type":"tool","name":"..."}` | Show `ToolCallBadge` inline |
| `done` | `{"type":"done","content":"..."}` | Mark message complete, hide cursor |
| `error` | `{"type":"error","message":"..."}` | Show error state in bubble |

---

### File Structure

```
app/copilot-agent-ui/
  package.json
  tsconfig.json
  next.config.ts
  tailwind.config.ts
  postcss.config.js
  .env.local.example
  README.md
  src/
    app/
      layout.tsx
      page.tsx                  ← redirect → /chat
      chat/
        page.tsx                ← two-column layout
    components/
      chat/
        ChatPanel.tsx
        MessageList.tsx
        MessageBubble.tsx       ← markdown + streaming cursor
        ToolCallBadge.tsx
        InputBar.tsx
      sidebar/
        Sidebar.tsx
        ConversationItem.tsx
      controls/
        AgentControls.tsx       ← agent/model/max-turns
    lib/
      api.ts
      sse.ts
      types.ts
    hooks/
      useAgentStream.ts
      useConversation.ts
```

---

### Verification Checklist

- [ ] `npm run dev` starts on `:3000` with no TypeScript/build errors
- [ ] Agent dropdown populates from `GET /agents` (backend on `:8000`)
- [ ] Send a message → SSE text chunks appear incrementally in the bubble
- [ ] Tool events show `ToolCallBadge` inline (e.g. `⚙ bash_exec`)
- [ ] Conversation sessions persist across page reload via `localStorage`
- [ ] Stop button aborts the in-flight stream cleanly

---

### Decisions

- **Auth**: Deferred (out of scope); UI has a placeholder comment where auth headers would go
- **API base URL**: `NEXT_PUBLIC_API_URL` env var (defaults to `http://localhost:8000`)
- **SSE transport**: `fetch()` + `ReadableStream`, not `EventSource`, because `/stream` is `POST`
- **Models** (hardcoded): `gpt-4o`, `gpt-4o-mini`, `claude-sonnet-4-6`, `claude-3-5-sonnet`
- **Styling**: Tailwind CSS only — no extra component library
- **Location**: `app/copilot-agent-ui/` as an independent sub-project (no coupling to the Python project)
