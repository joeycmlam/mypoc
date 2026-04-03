# myagent — CLI LLM Agent

A lightweight CLI tool to run an LLM agent with a custom system prompt, model, and instruction.

## Setup

```bash
cd app/myagent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-..."       # OpenAI
export ANTHROPIC_API_KEY="sk-ant-..." # Anthropic / Claude
export GEMINI_API_KEY="..."           # Google Gemini
```

## Usage

```
python agent.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream]
```

### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Path to the agent file (system prompt, `.md` or `.txt`) |
| `-m`, `--model` | LLM model name (default: `gpt-4o`). Any [litellm-supported model](https://docs.litellm.ai/docs/providers). |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn interactive chat session |
| `--no-stream` | Disable streaming; wait for the full response before printing |

## Examples

**Single-shot**
```bash
python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**Pipe from stdin**
```bash
cat my_code.py | python agent.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent.py -a agents/coder.md -m claude-3-5-sonnet-20241022 --interactive
```

**Use a different provider / model**
```bash
# Anthropic Claude
python agent.py -a agents/assistant.md -m claude-3-5-haiku-20241022 -i "Hello"

# Google Gemini
python agent.py -a agents/assistant.md -m gemini/gemini-1.5-pro -i "Hello"

# Local Ollama
python agent.py -a agents/assistant.md -m ollama/llama3 -i "Hello"
```

## Agent Files

An agent file is a plain text or Markdown file containing the system prompt.

```
agents/
  assistant.md   # General-purpose assistant
  coder.md       # Software engineering focused
```

Create your own agent file for any persona or task:

```markdown
# my_agent.md
You are a data scientist. Always respond with Python code using pandas and matplotlib.
Explain each step briefly.
```

Then run:
```bash
python agent.py -a agents/my_agent.md -m gpt-4o -i "Plot a sine wave"
```

## Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `reset` | Clear conversation history (keeps system prompt) |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |
