#!/usr/bin/env python3
"""
CLI Agent — GitHub Models (azure-ai-inference) edition.

Uses the GitHub Models endpoint with a GitHub personal access token
(GITHUB_TOKEN) so you can run any model available on github.com/marketplace/models.

Usage:
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"
  python agent.py -a agents/coder.md -m gpt-4o --interactive
  echo "Summarize this" | python agent.py -a agents/assistant.md -m gpt-4o

Required environment variable:
  GITHUB_TOKEN  — a GitHub personal access token with 'models:read' scope.
                  Create one at https://github.com/settings/tokens
"""

import argparse
import os
import sys
from pathlib import Path


GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_agent_file(path: str) -> str:
    agent_path = Path(path)
    if not agent_path.exists():
        print(f"Error: Agent file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    return agent_path.read_text(encoding="utf-8").strip()


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print(
            "Error: GITHUB_TOKEN environment variable is not set.\n"
            "Create a token at https://github.com/settings/tokens (needs 'models:read' scope).",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def build_client(token: str):
    """Return a ChatCompletionsClient pointed at the GitHub Models endpoint."""
    try:
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        print(
            "Error: azure-ai-inference is not installed.\n"
            "Run: pip install azure-ai-inference",
            file=sys.stderr,
        )
        sys.exit(1)

    return ChatCompletionsClient(
        endpoint=GITHUB_MODELS_ENDPOINT,
        credential=AzureKeyCredential(token),
    )


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _make_messages(system_prompt: str, history: list, user_text: str) -> list:
    from azure.ai.inference.models import SystemMessage, UserMessage

    return [SystemMessage(system_prompt), *history, UserMessage(user_text)]


def stream_completion(client, model: str, messages: list) -> str:
    """Stream response to stdout; return the full text."""
    from azure.core.exceptions import HttpResponseError

    full_text = ""
    try:
        response = client.complete(model=model, messages=messages, stream=True)
        for update in response:
            if update.choices and update.choices[0].delta:
                chunk = update.choices[0].delta.content or ""
                print(chunk, end="", flush=True)
                full_text += chunk
    except HttpResponseError as e:
        print(f"\nAPI error {e.status_code} ({e.reason}): {e.message}", file=sys.stderr)
        sys.exit(1)
    print()
    return full_text


def single_completion(client, model: str, messages: list) -> str:
    """Blocking (non-streaming) completion."""
    from azure.core.exceptions import HttpResponseError

    try:
        response = client.complete(model=model, messages=messages)
        return response.choices[0].message.content
    except HttpResponseError as e:
        print(f"API error {e.status_code} ({e.reason}): {e.message}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_once(client, system_prompt: str, model: str, instruction: str, stream: bool) -> None:
    """Single-turn: send one message and print the reply."""
    from azure.ai.inference.models import SystemMessage, UserMessage

    messages = [SystemMessage(system_prompt), UserMessage(instruction)]
    if stream:
        stream_completion(client, model, messages)
    else:
        print(single_completion(client, model, messages))


def run_interactive(client, system_prompt: str, model: str, stream: bool) -> None:
    """Multi-turn interactive chat session."""
    from azure.ai.inference.models import AssistantMessage, UserMessage

    history: list = []
    print(f"Agent ready  |  model: {model}  |  endpoint: {GITHUB_MODELS_ENDPOINT}")
    print("Commands: 'exit'/'quit' — stop  |  'reset' — clear history\n")

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

        if user_input.lower() == "reset":
            history.clear()
            print("[History cleared]\n")
            continue

        messages = _make_messages(system_prompt, history, user_input)
        print("Agent: ", end="", flush=True)

        if stream:
            reply = stream_completion(client, model, messages)
        else:
            reply = single_completion(client, model, messages)
            print(reply)

        # Keep conversation history for the next turn
        history.append(UserMessage(user_input))
        history.append(AssistantMessage(reply))
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="GitHub Models CLI agent (azure-ai-inference).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-shot
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"

  # Pipe instruction from stdin
  echo "Review this code" | python agent.py -a agents/coder.md -m gpt-4o

  # Interactive multi-turn chat
  python agent.py -a agents/coder.md -m gpt-4o --interactive

  # Use a different model (any name from github.com/marketplace/models)
  python agent.py -a agents/assistant.md -m meta-llama-3.1-70b-instruct -i "Hello"
  python agent.py -a agents/assistant.md -m mistral-large -i "Hello"

Environment:
  GITHUB_TOKEN  GitHub personal access token (models:read scope required).
                Create at https://github.com/settings/tokens
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
            "Model name as listed on github.com/marketplace/models "
            "(default: gpt-4o)."
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

    args = parser.parse_args()
    stream = not args.no_stream

    system_prompt = load_agent_file(args.agent_file)
    token = get_github_token()
    client = build_client(token)

    if args.interactive:
        run_interactive(client, system_prompt, args.model, stream)
    elif args.instruction:
        run_once(client, system_prompt, args.model, args.instruction, stream)
    elif not sys.stdin.isatty():
        instruction = sys.stdin.read().strip()
        if not instruction:
            print("Error: Empty instruction from stdin.", file=sys.stderr)
            sys.exit(1)
        run_once(client, system_prompt, args.model, instruction, stream)
    else:
        # No instruction and no pipe — default to interactive
        run_interactive(client, system_prompt, args.model, stream)

    client.close()


if __name__ == "__main__":
    main()
