# Plan: New Copilot-Agent with OpenAI SDK → api.githubcopilot.com

The existing `agent.py` uses the `azure-ai-inference` SDK against `https://models.inference.ai.azure.com`.
This plan creates a parallel `agent_copilot.py` using the **OpenAI Python SDK** against the **GitHub Copilot API** (`https://api.githubcopilot.com`), while bringing across all Phase 1–3 improvements from `plan-improveSubAgentOrchestration.prompt.md` (`invoke_agent` tool, `--max-turns` flag, smarter text-only abort, step-aware continuation prompts, updated `ba.agent.md`, `jira-test-automator.agent.md`). Keep `agent.py` untouched.

---

## Phase 0 – Dependencies & Project Setup

**Step 1** — Add `openai>=1.0` to `requirements.txt` and `pyproject.toml` under `copilot-agent/`.
- `requirements.txt`: add `openai>=1.0` (keep `azure-ai-inference` so existing agent continues to work)
- `pyproject.toml`: add to `dependencies` list; add entry_point `agent-copilot = copilot_agent.agent_copilot:main`
- *No dependencies*

---

## Phase 1 – Scaffold agent_copilot.py (SDK Migration)

**Step 2** — Create `app/copilot-agent/agent_copilot.py` with identical module layout to `agent.py`:
- Constants: `COPILOT_ENDPOINT = "https://api.githubcopilot.com"`, `MAX_TURNS_DEFAULT = 20`
- `load_agent_file()` — identical to `agent.py`
- `get_github_token()` — reads `GITHUB_TOKEN` env var (Copilot API uses GITHUB_TOKEN as Bearer token)
- `build_client(token)` — returns `openai.OpenAI(base_url=COPILOT_ENDPOINT, api_key=token)` instead of Azure `ChatCompletionsClient`
- `TOOLS` list — same JSON schema definitions as `agent.py`, **plus** the new `invoke_agent` tool (Step 3)
- *Depends on Step 1*

**Step 3** — Define `invoke_agent` tool schema in `TOOLS`:
```json
{
  "type": "function",
  "function": {
    "name": "invoke_agent",
    "description": "Delegate a sub-task to a specialised sub-agent defined by an agent file. Runs the sub-agent in isolation with its own conversation history. Returns the sub-agent's final text output.",
    "parameters": {
      "type": "object",
      "properties": {
        "agent_file": {
          "type": "string",
          "description": "Relative path to the .md agent file defining the sub-agent's system prompt."
        },
        "instruction": {
          "type": "string",
          "description": "The task to perform, passed as the user message to the sub-agent."
        },
        "context": {
          "type": "string",
          "description": "Optional additional data (e.g. Jira CLI output) injected before the instruction."
        }
      },
      "required": ["agent_file", "instruction"]
    }
  }
}
```
- *Parallel with Step 2*

---

## Phase 2 – OpenAI-Compatible Streaming Accumulator

**Step 4** — Implement `_accumulate_stream(stream) -> tuple[str, list[dict], str | None]` for the OpenAI SDK streaming format:
- Iterate `for chunk in stream` where each `chunk` is a `ChatCompletionChunk`
- `chunk.choices[0].delta.content` for text
- `chunk.choices[0].delta.tool_calls` — list of `ChoiceDeltaToolCall`; track by `.index` (not by `.id` as azure-ai-inference uses)
- Accumulate `id`, `name`, `arguments` per tool-call index into a dict keyed by index
- `chunk.choices[0].finish_reason` for termination
- Print reasoning tokens if present (`delta.reasoning_content`); guard with `getattr(delta, "reasoning_content", None)`
- *Depends on Step 2*

---

## Phase 3 – execute_tool with invoke_agent

**Step 5** — Implement `execute_tool(name, args, *, client, model, stream, depth=0) -> str`:
- `bash_exec` branch: identical to `agent.py` (`subprocess.run(shell=True, timeout=120)`)
- `invoke_agent` branch:
  - Guard: `if depth >= 2: return "[Error: max sub-agent recursion depth reached]"`
  - Load sub-agent system prompt via `load_agent_file(args["agent_file"])`
  - Build initial messages as plain dicts: optional `context` as `{"role":"user","content":"<context>"}`, then instruction as `{"role":"user","content":"<instruction>"}`
  - Call `run_agentic_loop(client, sub_prompt, model, initial_messages, stream, max_turns=10, depth=depth+1)`
  - Return the final string result
- *Depends on Steps 2, 3, 4*

---

## Phase 4 – Agentic Loop (OpenAI SDK + Loop Improvements)

**Step 6** — Implement `run_agentic_loop(client, system_prompt, model, initial_messages, stream, max_turns=20, depth=0) -> str`:

**OpenAI SDK message format** — use plain dicts throughout:
```python
history = [{"role": "system", "content": system_prompt}, *initial_messages]
```

**Non-streaming call** uses `client.chat.completions.create(model=model, messages=history, tools=TOOLS)`:
- `response.choices[0].message.content` for text
- `response.choices[0].message.tool_calls` — list of `ChatCompletionMessageToolCall` with `.id`, `.function.name`, `.function.arguments`

**Streaming call** uses `client.chat.completions.create(..., stream=True)` → `_accumulate_stream()`

**Assistant message with tool calls** appended as:
```python
{
  "role": "assistant",
  "content": content or None,
  "tool_calls": [
    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["args"]}}
    for tc in tool_calls_raw
  ]
}
```

**Tool result message**:
```python
{"role": "tool", "tool_call_id": tc["id"], "content": result}
```

**Loop improvements** (from `plan-improveSubAgentOrchestration.prompt.md`):
- `max_turns` parameter (default 20, configurable via `--max-turns` CLI arg, capped at 50)
- `_text_only_turns` abort: raise `_MAX_TEXT_ONLY` from 3 → 5 for top-level agents (`depth == 0`); keep at 3 for sub-agents (`depth > 0`)
- Text-only abort suppression: only count toward abort if content does NOT reference remaining steps — use `re.search(r'\bStep\s+[5-7]\b', content, re.IGNORECASE)` to detect pending steps
- Step-aware continuation prompt: when triggering continuation, inject: `"Step N was completed. Continue with Step N+1 now, using bash_exec or invoke_agent as required."` (parse last completed step from history keywords)

- *Depends on Steps 4, 5*

---

## Phase 5 – CLI Entry Point

**Step 7** — Implement `main()` with argparse, identical to `agent.py` plus:
- `--max-turns N` arg (`type=int`, default 20, `metavar="N"`, help: "Max tool-call turns (default 20, max 50)")
- Pass `max_turns=min(args.max_turns, 50)` to `run_agentic_loop`
- Help text updated to reference `api.githubcopilot.com` endpoint and note Copilot subscription requirement
- `run_once()` and `run_interactive()` factor out cleanly and pass `max_turns` through
- *Depends on Step 6*

---

## Phase 6 – Update Agent Prompts

**Step 8** — Update `agents/ba.agent.md`:
- **Step 1b**: replace `#file:` + "Read and adopt" wording → explicit `invoke_agent` call:
  `invoke_agent(agent_file="agents/jira-reader.md", context="<full CLI output>", instruction="Analyse this Jira ticket and return structured analysis")`
- **Step 3.4**: replace Test Designer persona-switch → `invoke_agent(agent_file="agents/test-designer.md", context="Ticket summary + FRs", instruction="Generate BDD test scenarios reformatted as AC-XX Given/When/Then with category tags")`
- **Step 5 (Jira update)**: prepend: `**MANDATORY — do not end the workflow without completing this step.** If running low on turns, skip optional analysis depth but always attempt the Jira update. Fallback: output the update text for manual copy-paste if the CLI fails.`
- **Step 7**: add `invoke_agent(agent_file="agents/jira-test-automator.agent.md", context="<ticket ID and BDD scenarios>", instruction="Generate automated test file for this ticket")` for optional test automation handoff
- *Depends on Phase 1 (invoke_agent in TOOLS)*; parallel with Step 9

**Step 9** — Update `agents/jira-test-automator.agent.md`:
- **Step 1**: replace `Read and adopt #file:app/copilot-agent/agents/test-designer.md` → `invoke_agent(agent_file="agents/test-designer.md", context="<Jira ticket content>", instruction="Fetch this ticket and produce requirements analysis + full BDD scenario set")`
- **Step 2**: replace Coder persona-switch → `invoke_agent(agent_file="agents/coder.md", context="<BDD scenarios from Step 1>", instruction="Implement every scenario as a pytest test function in test_<jira_key_lower>.py")`
- **Step 4**: replace Assistant persona-switch → `invoke_agent(agent_file="agents/assistant.md", context="<test file path + scenario count + gaps>", instruction="Write a concise summary report of the work completed")`
- *Parallel with Step 8*

---

## Relevant Files

| File | Action |
|---|---|
| `app/copilot-agent/agent_copilot.py` | **CREATE** — all implementation above |
| `app/copilot-agent/requirements.txt` | **EDIT** — add `openai>=1.0` (Step 1) |
| `app/copilot-agent/pyproject.toml` | **EDIT** — add openai dep + `agent-copilot` entry point (Step 1) |
| `app/copilot-agent/agents/ba.agent.md` | **EDIT** — update Steps 1b, 3.4, 5, 7 (Step 8) |
| `app/copilot-agent/agents/jira-test-automator.agent.md` | **EDIT** — update Steps 1, 2, 4 (Step 9) |
| `app/copilot-agent/agent.py` | **DO NOT MODIFY** |
| `app/copilot-agent/agents/jira-reader.md` | **DO NOT MODIFY** (leaf agent) |
| `app/copilot-agent/agents/test-designer.md` | **DO NOT MODIFY** (leaf agent) |
| `app/copilot-agent/agents/coder.md` | **DO NOT MODIFY** (leaf agent) |
| `app/copilot-agent/agents/assistant.md` | **DO NOT MODIFY** (leaf agent) |

---

## Verification

1. `pip install openai>=1.0` resolves without conflicts; `python agent_copilot.py --help` shows `--max-turns`
2. `python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Say hello"` — response arrives from `api.githubcopilot.com`
3. **`invoke_agent` smoke test**: prompt that triggers `invoke_agent` → verify sub-agent result is returned to parent and printed
4. **Recursion guard**: sub-agent at `depth >= 2` returns `[Error: max sub-agent recursion depth reached]`, no crash
5. **BA workflow end-to-end**: `python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "SCRUM-12" --max-turns 40` — all 7 steps complete including Jira update (Steps 5a + 5b)
6. **Text-only abort regression**: long analysis ticket runs through Step 5 without premature termination
7. **Turn exhaustion graceful degradation**: `--max-turns 10` exits cleanly with `[Warning: reached maximum tool-call turns]`
8. **Existing agent unchanged**: `python agent.py -a agents/assistant.md -m gpt-4o -i "Say hello"` still works

---

## Decisions

- **New file, not a refactor**: `agent_copilot.py` coexists with `agent.py`; existing code untouched
- **Same `GITHUB_TOKEN`**: Copilot API uses it as Bearer auth via `Authorization: Bearer <GITHUB_TOKEN>` — no new env var needed; note requires a Copilot subscription (not just `models:read` scope)
- **Plain-dict messages**: OpenAI SDK-idiomatic; simpler than azure-ai-inference SDK objects; sub-agents share the same format
- **`.index`-based streaming tool-call grouping**: OpenAI streaming chunks carry `.index` per tool-call delta (not empty-id heuristic used by azure-ai-inference)
- **Sub-agent turn budget**: 10 turns per sub-agent, independent of parent counter; not deducted from parent
- **Sequential sub-agents only**: no parallel execution (avoids interleaved output and thread-safety complexity)
- **Scope boundary**: `agent.py` and leaf agent files (`jira-reader.md`, `test-designer.md`, `coder.md`, `assistant.md`) unchanged

---

## Further Considerations

1. **Model name mapping**: Copilot API model names may differ from GitHub Models names (e.g. `claude-sonnet-4-6` vs `claude-3-5-sonnet`). Add a note to `--help` or README documenting Copilot-specific model name conventions. Default remains `gpt-4o`.
2. **GITHUB_TOKEN scope**: Document clearly that `api.githubcopilot.com` requires a Copilot subscription; a plain `models:read` PAT from GitHub Models will be rejected. CLI error message should surface a helpful hint.
3. **YAML frontmatter parsing**: `.agent.md` files have `agents:` and `tools:` fields. Should `agent_copilot.py` parse these to auto-restrict which tools a sub-agent may call? **Recommendation: Yes, as a follow-up.**
4. **Checkpoint/resume**: Save intermediate step output (FRs, ACs) to a temp file so failed runs can resume? **Recommendation: Defer** — increased `max_turns` + sub-agent isolation resolves most premature termination.
5. **Token budget awareness**: Warn when approaching context window limits? **Recommendation: Defer** — step-aware continuation addresses the symptom.
