#!/usr/bin/env python3
"""
FastAPI HTTP service wrapping AgentRunner from agent_copilot.py.

Endpoints:
  GET  /health           — liveness check
  GET  /agents           — list registered agents (from AgentRegistry) + all .md files
  GET  /agents/content   — return content + metadata for a specific agent file (?file=<name>)
  GET  /skills           — list registered skills (from SkillRegistry)
  POST /run              — blocking run, returns {"content": "..."}
  POST /stream           — SSE streaming run

Usage:
  python api_server.py [--host HOST] [--port PORT] [--reload]
  # or via entry point:
  agent-api [--host HOST] [--port PORT] [--reload]
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Optional

import frontmatter
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_copilot import AgentConfig, AgentRunner, CLI
from registry import AgentRegistry, SkillRegistry

_here = Path(__file__).parent
AGENTS_DIR = _here / "agents"
SKILLS_DIR = _here / "skills"

app = FastAPI(title="Copilot Agent API", version="1.0.0")

agent_registry = AgentRegistry(AGENTS_DIR)
skill_registry = SkillRegistry(SKILLS_DIR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    agent_file: str
    instruction: str
    model: str = "gpt-4o"
    max_turns: int = 20
    extra_context: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_agent_path(agent_file: str) -> Path:
    """Resolve and validate agent_file, guarding against path traversal."""
    resolved = (_here / agent_file).resolve()
    if not resolved.is_relative_to(_here.resolve()):
        raise HTTPException(status_code=400, detail="Invalid agent_file path.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Agent file '{agent_file}' not found.")
    return resolved


def _build_runner(req: RunRequest) -> AgentRunner:
    agent_path = _resolve_agent_path(req.agent_file)
    system_prompt = agent_path.read_text(encoding="utf-8").strip()
    config = AgentConfig(
        system_prompt=system_prompt,
        model=req.model,
        streaming=True,
        max_turns=min(req.max_turns, 50),
        base_dir=_here,
    )
    return AgentRunner(config)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/agents")
async def list_agents():
    registered = [
        {"id": a.id, "name": a.name, "description": a.description,
         "skills": a.skills, "tools": a.tools}
        for a in agent_registry.all().values()
    ]
    # also surface unregistered .md files for backward compatibility
    all_files = sorted(p.name for p in AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []
    return {"agents": registered, "files": all_files}


@app.get("/agents/content")
async def agent_content(file: str = Query(..., description="Agent filename, e.g. ba.agent.md")):
    """Return the system prompt content and frontmatter metadata for a given agent file."""
    path = _resolve_agent_path(f"agents/{file}")
    try:
        post = frontmatter.load(str(path))
        return {
            "file": file,
            "content": post.content,
            "metadata": dict(post.metadata),
        }
    except Exception:
        raw = path.read_text(encoding="utf-8")
        return {"file": file, "content": raw, "metadata": {}}


@app.get("/skills")
async def list_skills():
    return {
        "skills": [
            {"id": s.id, "name": s.name, "description": s.description}
            for s in skill_registry.all().values()
        ]
    }


@app.post("/run")
async def run_agent(req: RunRequest):
    runner = _build_runner(req)
    result = await runner.run(
        req.instruction,
        extra_context=req.extra_context or "",
    )
    return {"content": result}


@app.post("/stream")
async def stream_agent(req: RunRequest):
    runner = _build_runner(req)
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_chunk(chunk: str) -> None:
        if chunk:
            queue.put_nowait(json.dumps({"type": "chunk", "content": chunk}))

    def on_tool(name: str) -> None:
        if name:
            queue.put_nowait(json.dumps({"type": "tool", "name": name}))

    async def _run_and_signal() -> None:
        try:
            result = await runner.run(
                req.instruction,
                extra_context=req.extra_context or "",
                on_chunk=on_chunk,
                on_tool=on_tool,
            )
            queue.put_nowait(json.dumps({"type": "done", "content": result}))
        except Exception as exc:
            queue.put_nowait(json.dumps({"type": "error", "message": str(exc)}))
        finally:
            queue.put_nowait(None)  # sentinel

    async def _generate():
        task = asyncio.create_task(_run_and_signal())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-api",
        description="Copilot Agent API server (FastAPI + uvicorn).",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode).")
    args = parser.parse_args()
    uvicorn.run("api_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    cli_main()
