# copilot-agent — GitHub Models CLI Agent

A CLI agent built on the **[azure-ai-inference](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-inference)** Python SDK — the official SDK for the [GitHub Models](https://github.com/marketplace/models) endpoint.

Authenticate with a GitHub personal access token and talk to any model available in the GitHub Marketplace (GPT-4o, Mistral, Llama, Phi, and more).

## Setup

```bash
cd app/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your GitHub token as an environment variable:

```bash
export GITHUB_TOKEN="github_pat_..."
```

> Create a token at <https://github.com/settings/tokens> — only **`models:read`** scope is needed.

## Usage

```
python agent.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream]
```

### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Agent Markdown/text file containing the system prompt |
| `-m`, `--model` | Model name from [github.com/marketplace/models](https://github.com/marketplace/models) (default: `gpt-4o`) |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn chat session |
| `--no-stream` | Disable streaming; wait for the full response |

## Examples

**Single-shot**
```bash
python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**Pipe from stdin**
```bash
cat main.py | python agent.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent.py -a agents/coder.md -m gpt-4o --interactive
```

**Different models** (any name from the GitHub Marketplace):
```bash
python agent.py -a agents/assistant.md -m mistral-large -i "Hello"
python agent.py -a agents/assistant.md -m meta-llama-3.1-70b-instruct -i "Hello"
python agent.py -a agents/assistant.md -m Phi-3.5-MoE-instruct -i "Hello"
```

## Agent Files

An agent file is a plain text or Markdown file that becomes the **system prompt**.

```
agents/
  assistant.md   # General-purpose assistant
  coder.md       # Software engineering focused
```

Create your own for any persona or task:

```markdown
# agents/data_scientist.md
You are a senior data scientist. Respond with concise Python code using
pandas and matplotlib. Explain each step briefly.
```

Then run:
```bash
python agent.py -a agents/data_scientist.md -m gpt-4o -i "Plot a sine wave"
```

## Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `reset` | Clear conversation history (keeps system prompt) |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |

## Available Models

Browse all available models at <https://github.com/marketplace/models>.  
Notable ones include:

| Model | Provider |
|-------|----------|
| `gpt-4o` | OpenAI |
| `gpt-4o-mini` | OpenAI |
| `mistral-large` | Mistral |
| `meta-llama-3.1-70b-instruct` | Meta |
| `Phi-3.5-MoE-instruct` | Microsoft |
| `AI21-Jamba-1.5-Large` | AI21 Labs |
