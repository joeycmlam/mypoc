#!/usr/bin/env python3
"""
CLI Agent — Run an LLM agent with a custom agent file, model, and instruction.

Usage:
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"
  python agent.py -a agents/coder.md -m claude-3-5-sonnet-20241022 --interactive
  echo "Summarize this text" | python agent.py -a agents/assistant.md -m gpt-4o
"""

import argparse
import sys
from pathlib import Path


def load_agent_file(path: str) -> str:
    agent_path = Path(path)
    if not agent_path.exists():
        print(f"Error: Agent file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    return agent_path.read_text(encoding="utf-8").strip()


def get_litellm():
    try:
        import litellm
        return litellm
    except ImportError:
        print("Error: litellm is not installed. Run: pip install litellm", file=sys.stderr)
        sys.exit(1)


def stream_completion(litellm, model: str, messages: list) -> str:
    """Stream a completion and return the full response text."""
    full_response = ""
    try:
        response = litellm.completion(model=model, messages=messages, stream=True)
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
                full_response += delta
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    print()
    return full_response


def single_completion(litellm, model: str, messages: list) -> str:
    """Fetch a completion without streaming and return the response text."""
    try:
        response = litellm.completion(model=model, messages=messages)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_once(system_prompt: str, model: str, instruction: str, stream: bool) -> None:
    """Run a single-turn agent call."""
    litellm = get_litellm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction},
    ]
    if stream:
        stream_completion(litellm, model, messages)
    else:
        print(single_completion(litellm, model, messages))


def run_interactive(system_prompt: str, model: str, stream: bool) -> None:
    """Run a multi-turn interactive chat session."""
    litellm = get_litellm()
    messages = [{"role": "system", "content": system_prompt}]

    print(f"Agent ready  |  model: {model}")
    print("Type 'exit' or 'quit' to stop, 'reset' to clear history.\n")

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
            messages = [{"role": "system", "content": system_prompt}]
            print("[History cleared]\n")
            continue

        messages.append({"role": "user", "content": user_input})
        print("Agent: ", end="", flush=True)

        if stream:
            reply = stream_completion(litellm, model, messages)
        else:
            reply = single_completion(litellm, model, messages)
            print(reply)

        messages.append({"role": "assistant", "content": reply})
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Run an LLM agent with a custom agent file, model, and instruction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-shot mode
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"

  # Pipe instruction from stdin
  echo "Summarize this" | python agent.py -a agents/assistant.md -m gpt-4o

  # Interactive multi-turn mode
  python agent.py -a agents/coder.md -m claude-3-5-sonnet-20241022 --interactive

  # Disable streaming
  python agent.py -a agents/assistant.md -m gpt-4o -i "Hello" --no-stream

Environment Variables:
  OPENAI_API_KEY        — for OpenAI models (gpt-4o, gpt-4-turbo, etc.)
  ANTHROPIC_API_KEY     — for Anthropic models (claude-*)
  GEMINI_API_KEY        — for Google models (gemini-*)
  AZURE_API_KEY         — for Azure OpenAI models
  OPENAI_API_BASE       — custom base URL for OpenAI-compatible endpoints
""",
    )

    parser.add_argument(
        "-a", "--agent-file",
        required=True,
        metavar="FILE",
        help="Path to the agent file containing the system prompt (.md or .txt)",
    )
    parser.add_argument(
        "-m", "--model",
        default="gpt-4o",
        metavar="MODEL",
        help="LLM model to use (default: gpt-4o). Supports any litellm-compatible model name.",
    )
    parser.add_argument(
        "-i", "--instruction",
        metavar="TEXT",
        help="User instruction/prompt. Reads from stdin if omitted and stdin is piped.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive multi-turn chat session.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output (wait for full response).",
    )

    args = parser.parse_args()
    stream = not args.no_stream
    system_prompt = load_agent_file(args.agent_file)

    if args.interactive:
        run_interactive(system_prompt, args.model, stream)
    elif args.instruction:
        run_once(system_prompt, args.model, args.instruction, stream)
    elif not sys.stdin.isatty():
        instruction = sys.stdin.read().strip()
        if not instruction:
            print("Error: Empty instruction from stdin.", file=sys.stderr)
            sys.exit(1)
        run_once(system_prompt, args.model, instruction, stream)
    else:
        # No instruction given and no pipe — default to interactive
        run_interactive(system_prompt, args.model, stream)


if __name__ == "__main__":
    main()
