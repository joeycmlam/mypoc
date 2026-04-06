#!/usr/bin/env python3
"""
CLI Agent — GitHub Copilot SDK edition.

Uses the official `github-copilot-sdk` Python package, which delegates to the
GitHub Copilot CLI running locally.  No GITHUB_TOKEN or API key is required —
authentication is handled by the Copilot CLI's own credential store.

Key differences from agent.py (azure-ai-inference):
  - SDK:      github-copilot-sdk  (not azure-ai-inference)
  - Auth:     Copilot CLI credential store  (no GITHUB_TOKEN needed at runtime)
  - Async:    asyncio / async-await throughout
  - Events:   event-driven session model (session.idle signals turn completion)
  - Streaming: assistant.message.delta events
  - Tools:    registered via define_tool() at session creation
  - New tool: invoke_agent — real sub-agent delegation, isolated session+turn budget
  - Loop:     smarter text-only abort, step-aware continuation, --max-turns

Prerequisites:
  pip install github-copilot-sdk
  # GitHub Copilot CLI must be installed and authenticated:
  gh extension install github/gh-copilot
  gh auth login

Usage:
  python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"
  python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "please analyze the jira SCRUM-12" --max-turns 40
  python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive
  echo "Summarize this" | python agent_copilot.py -a agents/assistant.md -m gpt-4o
"""

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env files for Jira credentials, but do NOT let a pre-existing GITHUB_TOKEN
# interfere with the Copilot CLI's own OAuth credential store.
# The Copilot CLI only accepts OAuth tokens from gh/Copilot CLI app; a PAT with
# insufficient scopes causes "Authorization error, you may need to run /login".
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / "jira-cli" / ".env")

# Remove GITHUB_TOKEN / GH_TOKEN so the Copilot CLI uses its keyring credentials.
for _env_key in ("GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN"):
    os.environ.pop(_env_key, None)


MAX_TURNS_DEFAULT = 20
MAX_TURNS_LIMIT = 50
SUB_AGENT_MAX_TURNS = 10
MAX_RECURSION_DEPTH = 2

_STEP_RE = re.compile(r"\bStep\s+(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Turn state
# ---------------------------------------------------------------------------

@dataclass
class _TurnState:
    """Mutable state collected during a single assistant turn."""
    content_parts: list[str] = field(default_factory=list)
    tool_called: bool = False
    done: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def content(self) -> str:
        return "".join(self.content_parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_agent_file(path: str) -> str:
    agent_path = Path(path)
    if not agent_path.exists():
        print(f"Error: Agent file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    return agent_path.read_text(encoding="utf-8").strip()


def _check_sdk() -> None:
    try:
        import copilot  # noqa: F401
    except ImportError:
        print(
            "Error: github-copilot-sdk is not installed.\n"
            "Run: pip install github-copilot-sdk\n"
            "Also ensure the GitHub Copilot CLI is installed and authenticated:\n"
            "  gh extension install github/gh-copilot && gh auth login",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Tool definitions (JSON schema for the model)
# ---------------------------------------------------------------------------

BASH_EXEC_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute.",
        }
    },
    "required": ["command"],
}

INVOKE_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_file": {
            "type": "string",
            "description": (
                "Relative path to the .md agent file defining the sub-agent's "
                "system prompt (e.g. 'agents/jira-reader.md')."
            ),
        },
        "instruction": {
            "type": "string",
            "description": "The task to perform, passed as the user message to the sub-agent.",
        },
        "context": {
            "type": "string",
            "description": (
                "Optional additional data (e.g. Jira CLI output, requirements text) "
                "injected as a user message before the instruction."
            ),
        },
    },
    "required": ["agent_file", "instruction"],
}


# ---------------------------------------------------------------------------
# bash_exec handler
# ---------------------------------------------------------------------------

async def _handle_bash_exec(inv) -> object:
    """ToolHandler: receives ToolInvocation, returns ToolResult."""
    from copilot.tools import ToolResult

    args = inv.arguments or {}
    command = args.get("command", "")
    if not command:
        return ToolResult(text_result_for_llm="[Error: no command provided]", result_type="failure")
    print(f"\n\033[36m[Tool: bash_exec]\033[0m {command}", flush=True)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(text_result_for_llm="[Error: command timed out after 120s]", result_type="failure")

        output = stdout_bytes.decode(errors="replace")
        if stderr_bytes:
            output += f"\n[stderr]: {stderr_bytes.decode(errors='replace')}"
        if proc.returncode != 0:
            output += f"\n[exit code: {proc.returncode}]"
        text = output.strip() or "(no output)"
        print(f"\033[33m[Result]\033[0m\n{text}\n", flush=True)
        return ToolResult(text_result_for_llm=text)
    except Exception as exc:
        return ToolResult(text_result_for_llm=f"[Error: {exc}]", result_type="failure")


# ---------------------------------------------------------------------------
# Step-aware helpers
# ---------------------------------------------------------------------------

def _last_completed_step(messages: list[str]) -> int | None:
    """Scan assistant messages in reverse to find the highest mentioned step number."""
    highest = None
    for text in reversed(messages):
        for m in _STEP_RE.finditer(text):
            n = int(m.group(1))
            if highest is None or n > highest:
                highest = n
    return highest


def _has_pending_steps(content: str) -> bool:
    """Return True if content references step numbers ≥ 5 (likely not yet executed)."""
    return bool(re.search(r"\bStep\s+[5-9]\b", content, re.IGNORECASE))


def _is_mid_workflow(content: str) -> bool:
    has_bash_blocks = bool(re.search(r"```(?:bash|sh)\b", content))
    has_signal = bool(re.search(
        r"\b(next[,\s]|please wait|i will now|i will next|let me now|"
        r"proceeding to|moving to step|continuing|i'll now|i'll next)\b",
        content,
        re.IGNORECASE,
    ))
    return has_bash_blocks or has_signal or _has_pending_steps(content)


def _continuation_prompt(assistant_messages: list[str]) -> str:
    """Build the continuation message based on the last completed step."""
    last_step = _last_completed_step(assistant_messages)
    if last_step is not None:
        return (
            f"Step {last_step} was completed. "
            f"Continue with Step {last_step + 1} now, "
            "executing all required commands via bash_exec or invoke_agent."
        )
    return (
        "Please continue and complete the remaining steps, "
        "executing all required commands via bash_exec or invoke_agent."
    )


# ---------------------------------------------------------------------------
# Sub-agent handler factory, tool builder, and event handler
# ---------------------------------------------------------------------------

def _make_invoke_agent_handler(model: str, streaming: bool, depth: int):
    """Return a ToolHandler for invoke_agent bound to the given runtime context."""
    async def _handle(inv) -> object:
        from copilot.tools import ToolResult

        if depth >= MAX_RECURSION_DEPTH:
            return ToolResult(
                text_result_for_llm="[Error: max sub-agent recursion depth reached]",
                result_type="failure",
            )

        args = inv.arguments or {}
        agent_file = args.get("agent_file", "")
        instruction = args.get("instruction", "")
        context = args.get("context", "")

        if not agent_file:
            return ToolResult(
                text_result_for_llm="[Error: invoke_agent requires 'agent_file']",
                result_type="failure",
            )
        if not instruction:
            return ToolResult(
                text_result_for_llm="[Error: invoke_agent requires 'instruction']",
                result_type="failure",
            )

        sub_prompt = load_agent_file(str(_here / agent_file))
        print(f"\n\033[35m[Sub-agent: {agent_file}]\033[0m depth={depth + 1}", flush=True)
        result = await run_agentic_loop(
            system_prompt=sub_prompt,
            model=model,
            initial_prompt=instruction,
            streaming=streaming,
            max_turns=SUB_AGENT_MAX_TURNS,
            depth=depth + 1,
            extra_context=context,
        )
        print(f"\033[35m[Sub-agent: {agent_file} complete]\033[0m\n", flush=True)
        return ToolResult(text_result_for_llm=result or "(sub-agent returned no output)")

    return _handle


def _build_tools(model: str, streaming: bool, depth: int) -> list:
    """Build the tool list for a session at the given recursion depth."""
    from copilot.tools import Tool

    return [
        Tool(
            name="bash_exec",
            description=(
                "Execute a shell command and return its stdout/stderr. "
                "Use this to run the Jira CLI, read files, or perform any "
                "shell operation required by the workflow."
            ),
            parameters=BASH_EXEC_SCHEMA,
            handler=_handle_bash_exec,
            skip_permission=True,
        ),
        Tool(
            name="invoke_agent",
            description=(
                "Delegate a sub-task to a specialised sub-agent defined by an agent file. "
                "Runs the sub-agent in isolation with its own conversation history and turn budget. "
                "Returns the sub-agent's final text output as a string. "
                "Use this instead of reading agent files inline or switching persona."
            ),
            parameters=INVOKE_AGENT_SCHEMA,
            handler=_make_invoke_agent_handler(model, streaming, depth),
            skip_permission=True,
        ),
    ]


def _make_event_handler(state: _TurnState, streaming: bool):
    """Return an event handler that populates *state* for a single assistant turn."""
    from copilot.session import SessionEventType

    def _handler(event):
        et = event.type
        if streaming and et == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            chunk = getattr(event.data, "delta_content", "") or ""
            print(chunk, end="", flush=True)
            state.content_parts.append(chunk)
        elif et == SessionEventType.ASSISTANT_MESSAGE:
            content = getattr(event.data, "content", "") or ""
            if not streaming:
                print(content)
            state.content_parts.append(content)
        elif et in (SessionEventType.TOOL_EXECUTION_START, SessionEventType.TOOL_EXECUTION_COMPLETE):
            state.tool_called = True
        elif et == SessionEventType.SESSION_IDLE:
            state.done.set()
        elif et == SessionEventType.SESSION_ERROR:
            print(
                f"\n[Session error]: {getattr(event.data, 'message', str(event.data))}",
                file=sys.stderr,
            )
            state.done.set()

    return _handler


# ---------------------------------------------------------------------------
# Core agentic loop (one CopilotClient session per invocation)
# ---------------------------------------------------------------------------

async def run_agentic_loop(
    system_prompt: str,
    model: str,
    initial_prompt: str,
    streaming: bool,
    max_turns: int = MAX_TURNS_DEFAULT,
    depth: int = 0,
    extra_context: str = "",
) -> str:
    """
    Run an agentic loop using the GitHub Copilot SDK.

    Each invocation creates its own CopilotClient + Session so sub-agents are
    fully isolated (independent history and turn budget).
    """
    from copilot import CopilotClient
    from copilot.session import PermissionHandler

    _MAX_TEXT_ONLY = 3 if depth > 0 else 5
    _text_only_turns = 0
    _turn = 0
    _assistant_messages: list[str] = []
    last_content = ""

    first_prompt = f"{extra_context}\n\n{initial_prompt}" if extra_context else initial_prompt
    tools = _build_tools(model, streaming, depth)

    async with CopilotClient() as client:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model,
            streaming=streaming,
            tools=tools,
            system_message={"mode": "replace", "content": system_prompt},
        )

        while _turn < max_turns:
            state = _TurnState()
            unsubscribe = session.on(_make_event_handler(state, streaming))

            prompt = first_prompt if _turn == 0 else _continuation_prompt(_assistant_messages)
            await session.send(prompt)
            await state.done.wait()
            unsubscribe()

            if streaming and state.content:
                print()

            last_content = state.content
            if state.content:
                _assistant_messages.append(state.content)

            _turn += 1

            if state.tool_called:
                _text_only_turns = 0
                continue

            if _is_mid_workflow(state.content) and _text_only_turns < _MAX_TEXT_ONLY:
                _text_only_turns += 1
                continue

            break

        await session.disconnect()

    if _turn >= max_turns:
        print("[Warning: reached maximum tool-call turns]", file=sys.stderr)

    return last_content


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

async def run_once_async(
    system_prompt: str, model: str, instruction: str, streaming: bool, max_turns: int
) -> None:
    await run_agentic_loop(
        system_prompt=system_prompt,
        model=model,
        initial_prompt=instruction,
        streaming=streaming,
        max_turns=max_turns,
    )


async def run_interactive_async(
    system_prompt: str, model: str, streaming: bool, max_turns: int
) -> None:
    print(f"Agent ready  |  model: {model}  |  sdk: github-copilot-sdk")
    print("Commands: 'exit'/'quit' — stop\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        print("Agent: ", end="", flush=True)
        await run_agentic_loop(
            system_prompt=system_prompt,
            model=model,
            initial_prompt=user_input,
            streaming=streaming,
            max_turns=max_turns,
        )
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-copilot",
        description="GitHub Copilot SDK CLI agent (github-copilot-sdk).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-shot
  python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"

  # BA workflow with extended turn budget
  python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "SCRUM-12" --max-turns 40

  # Pipe instruction from stdin
  echo "Review this code" | python agent_copilot.py -a agents/coder.md -m gpt-4o

  # Interactive multi-turn chat
  python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive

  # Use a different model (any model available via Copilot CLI)
  python agent_copilot.py -a agents/assistant.md -m claude-sonnet-4-6 -i "Hello"

Prerequisites:
  pip install github-copilot-sdk
  gh extension install github/gh-copilot
  gh auth login
""",
    )

    parser.add_argument(
        "-a", "--agent-file",
        required=True,
        metavar="FILE",
        help="Path to the agent Markdown/text file containing the system prompt.",
    )
    parser.add_argument(
        "-m", "--model",
        default="gpt-4o",
        metavar="MODEL",
        help=(
            "Model name as available via the Copilot CLI "
            "(default: gpt-4o). Examples: claude-sonnet-4-6, gpt-4o."
        ),
    )
    parser.add_argument(
        "-i", "--instruction",
        metavar="TEXT",
        help="User instruction / prompt (single-shot mode). Reads from stdin if omitted and stdin is piped.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive multi-turn chat session.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming; wait for the full response before printing.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=MAX_TURNS_DEFAULT,
        metavar="N",
        help=(
            f"Maximum turns per run (default {MAX_TURNS_DEFAULT}, "
            f"max {MAX_TURNS_LIMIT}). "
            "Increase for complex multi-step workflows like the BA agent."
        ),
    )

    args = parser.parse_args()
    streaming = not args.no_stream
    max_turns = min(args.max_turns, MAX_TURNS_LIMIT)

    _check_sdk()
    system_prompt = load_agent_file(args.agent_file)

    if args.interactive:
        asyncio.run(run_interactive_async(system_prompt, args.model, streaming, max_turns))
    elif args.instruction:
        asyncio.run(run_once_async(system_prompt, args.model, args.instruction, streaming, max_turns))
    elif not sys.stdin.isatty():
        instruction = sys.stdin.read().strip()
        if not instruction:
            print("Error: Empty instruction from stdin.", file=sys.stderr)
            sys.exit(1)
        asyncio.run(run_once_async(system_prompt, args.model, instruction, streaming, max_turns))
    else:
        asyncio.run(run_interactive_async(system_prompt, args.model, streaming, max_turns))


if __name__ == "__main__":
    main()
