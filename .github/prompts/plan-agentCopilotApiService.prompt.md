# Plan: REST API Service for `agent_copilot.py`

In addition to the existing CLI agent, please support in a **FastAPI HTTP service** by adding a new `api_server.py` module that reuses `AgentRunner`, `AgentConfig`, `BashTool`, and `WorkflowAnalyser` unchanged. The only modification to `agent_copilot.py` is a tiny `on_chunk` callback hook to bridge streaming to SSE.

---

## Phase 1 — Minimal change to `agent_copilot.py`

1. Add optional `on_chunk: Callable[[str], None] | None = None` to `AgentRunner.run()` signature.
2. Thread it into `_make_event_handler()`: when set, call `on_chunk(chunk)` instead of `print(chunk)` for `ASSISTANT_MESSAGE_DELTA` events.

*This is the only change to the existing file.*

---

## Phase 2 — New `api_server.py`

3. Pydantic request model `RunRequest`: `agent_file`, `instruction`, `model` (default `gpt-4o`), `max_turns` (default `20`), `extra_context` (optional).
4. Endpoints:
   - `GET /health` → `{"status": "ok"}`
   - `GET /agents` → list of `.md` files under `agents/`
   - `POST /run` → non-streaming; awaits `AgentRunner.run()`, returns `{"content": "..."}` JSON
   - `POST /stream` → `text/event-stream` SSE: creates `asyncio.Queue`, passes `on_chunk=queue.put_nowait` to `run()`, streams `data: {"type":"chunk","content":"..."}\n\n` and a final `data: {"type":"done","content":"..."}\n\n`
5. `CORSMiddleware` with `allow_origins=["*"]` (internal-only, no auth).
6. `cli_main()` entry point: `uvicorn.run()` with `--host`/`--port`/`--reload` args.

---

## Phase 3 — `requirements.txt` + `pyproject.toml`

7. Add `fastapi>=0.111` and `uvicorn[standard]>=0.29` to both files.
8. Add script entry point `agent-api = "api_server:cli_main"` in `pyproject.toml`.

---

## Phase 4 — `Dockerfile`

9. Copy `api_server.py` in the builder stage (alongside `agent_copilot.py`).
10. Add `EXPOSE 8000`.
11. Keep existing `ENTRYPOINT ["copilot-agent"]` as CLI default; add a commented override for API mode:
    ```
    # To run as API: docker run -p 8000:8000 <image> uvicorn api_server:app --host 0.0.0.0 --port 8000
    ```

---

## Relevant files

- `app/copilot-agent/agent_copilot.py` — add `on_chunk` to `AgentRunner.run()` + `_make_event_handler()`
- `app/copilot-agent/api_server.py` — **[NEW]** FastAPI app
- `app/copilot-agent/requirements.txt` — add `fastapi`, `uvicorn[standard]`
- `app/copilot-agent/pyproject.toml` — add deps + `agent-api` script
- `app/copilot-agent/Dockerfile` — copy `api_server.py`, `EXPOSE 8000`

---

## Verification

1. `pip install fastapi uvicorn[standard]` then `python api_server.py` — server starts on `:8000`
2. `curl http://localhost:8000/health` → `{"status":"ok"}`
3. `curl http://localhost:8000/agents` → JSON list of agent files
4. `curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'` → JSON response
5. `curl -N -X POST http://localhost:8000/stream -H "Content-Type: application/json" -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'` → SSE chunks visible in terminal

---

## Decisions / Scope

- `turns_used` is deliberately excluded from the response (YAGNI — not needed now, easy to add later).
- No authentication (internal/trusted network deployment).
- SSE tool events: optionally emit `data: {"type":"tool","name":"..."}\n\n` for observability — hookable via a second optional `on_tool` callback on `AgentRunner.run()`.
- `agents/` base dir is relative to `api_server.py` file location (consistent with CLI's `_here`).
