# Plan: Improve copilot-agent Sub-Agent Orchestration

The BA agent (`ba.agent.md`) runs a 7-step workflow orchestrating sub-agents (jira-reader, test-designer, jira-test-automator), but `agent.py` has no real sub-agent mechanism — it's a single agentic loop with a 20-turn limit and a fragile auto-continue heuristic. Long multi-step workflows exhaust turns or stall on text-only analysis turns before reaching Step 5 (Jira update). The fix: add a real `invoke_agent` tool, step-tracking, and smarter loop management.

---

## Root Cause Analysis

1. **No real sub-agent tool**: The `#file:` references in agent prompts are VS Code Copilot syntax — `agent.py` doesn't understand them. The model can only `bash_exec` to `cat` the file, then "pretend" to switch persona. This wastes turns and context.
2. **20-turn ceiling too low**: The BA workflow has 7 steps; Steps 1 and 3.4 each involve sub-agent delegation. Fetching Jira + analyzing + writing FRs + BDD scenarios + reformatting ACs + updating Jira easily needs 15-30+ tool calls.
3. **3-consecutive-text-only abort**: Steps 2, 3.1-3.3 are analysis/writing-heavy — the model produces long text without tool calls. After 3 such turns the loop terminates, often before Step 5.
4. **Context window pressure**: Accumulated history (system prompt + all tool results + generated text) can exceed the model's window, degrading later steps.
5. **No progress tracking**: The loop doesn't know which workflow step the agent is on, so it can't prioritize remaining steps or detect premature termination.

---

## Steps

### Phase 1: Add `invoke_agent` Tool (Core Sub-Agent Mechanism)

1. **Define `invoke_agent` tool schema** — Add to the `TOOLS` list in `agent.py`. Parameters: `agent_file` (path to .md), `instruction` (task for the sub-agent), `model` (optional, defaults to parent). *No dependencies.*

2. **Implement `invoke_agent` execution** — In `execute_tool()`: load sub-agent system prompt, create fresh history, run `run_agentic_loop()` recursively, return sub-agent's final output as tool result. Cap recursion depth (max 2 levels). *Depends on 1.*

3. **Pass shared context to sub-agents** — Sub-agent inherits same `client`/`model`/env. Add an optional `context` parameter so parents can inject data (ticket content, requirements) without the sub-agent re-fetching. *Depends on 2.*

### Phase 2: Improve Loop Resilience

4. **Make turn limit configurable** — Add `--max-turns` CLI arg (default 20, up to 50). Complex orchestrators like BA need more headroom. *Parallel with Phase 1.*

5. **Fix text-only abort for orchestrator agents** — The 3-consecutive-text-only limit prematurely kills long analysis steps. Fix by: increasing threshold for orchestrator agents, only counting toward abort if the model signals completion (final checklist/summary) rather than just producing analysis text, and checking if remaining steps are referenced but not yet executed. *Parallel with Phase 1.*

6. **Add step-aware continuation prompt** — When the model pauses mid-workflow: parse the system prompt for numbered steps, scan history for evidence of completion (keywords like "Step 5", `--update-description`, `--add-comment`), inject: "Steps 5, 6 not yet complete. Continue with Step 5." *Depends on 5.*

### Phase 3: Update Agent Prompts

7. **Update `ba.agent.md`** — Replace `#file:` + "Read and adopt" language with explicit `invoke_agent` tool invocations for Steps 1, 3.4, and 7. *Depends on Phase 1.*

8. **Update `jira-test-automator.agent.md`** — Same pattern: replace persona-switching with `invoke_agent` calls for Test Designer, Coder, and Assistant steps. *Parallel with 7.*

9. **Add Jira update resilience to `ba.agent.md`** — Explicit instructions: "Step 5 is MANDATORY — do not end without attempting it." If running low on turns, skip optional analysis depth and prioritize Jira update. Fallback: output text for manual copy-paste if CLI fails. *Parallel with 7.*

### Phase 4: Optional Enhancements

10. **`--context-file` CLI arg** — Pass a file injected as initial context to sub-agents. *Low priority, parallel.*

11. **Step-completion logging** — Print `[Step N/M complete]` markers to stderr. *Low priority, parallel.*

---

## Relevant Files

- `app/copilot-agent/agent.py` — Core changes: `invoke_agent` tool definition (TOOLS list ~L37), implementation (~L109 `execute_tool()`), loop improvements (~L197 `run_agentic_loop()`), `--max-turns` CLI arg (~L369 `main()`)
- `app/copilot-agent/agents/ba.agent.md` — Rewrite Steps 1, 3.4, 5, 7 to use `invoke_agent`; add mandatory Jira update instructions
- `app/copilot-agent/agents/jira-test-automator.agent.md` — Rewrite Steps 1, 2, 4 to use `invoke_agent`
- `app/copilot-agent/agents/test-designer.md` — No structural changes (leaf agent)
- `app/copilot-agent/agents/jira-reader.md` — No changes (leaf agent)
- `app/copilot-agent/agents/coder.md` — No changes (leaf agent)

---

## Verification

1. **Unit test `invoke_agent`**: Call `execute_tool("invoke_agent", {"agent_file": "agents/assistant.md", "instruction": "Say hello"})` — verify it returns a response
2. **Recursion depth test**: Sub-agent invoking beyond max depth returns an error, not a crash
3. **End-to-end BA workflow**: `python agent.py -a agents/ba.agent.md -m gpt-4o -i "SCRUM-12" --max-turns 40` — verify all 6 steps complete including Jira update (Steps 5a + 5b)
4. **Text-only abort regression**: Run with a ticket producing lengthy analysis — verify loop doesn't abort before Step 5
5. **Turn exhaustion**: Test with `--max-turns 10` for graceful degradation

---

## Decisions

- **Sub-agent isolation**: Fresh conversation history per sub-agent (not the parent's). Parent passes context explicitly via `instruction` + `context`. Prevents context window blowup.
- **Sub-agent turn budget**: Own counter (default 10 turns), not deducted from parent's budget.
- **Sequential execution**: No parallel sub-agents (avoids thread safety / interleaved output complexity).
- **Backward compatible**: `invoke_agent` is additive; existing prompts continue to work.
- **Scope boundary**: No Jira CLI changes, no model/endpoint changes, no streaming refactor.

---

## Further Considerations

1. **Agent prompt frontmatter parsing**: `.agent.md` files have YAML frontmatter with `agents:` and `tools:` fields. Should `agent.py` parse this to auto-discover sub-agents and enforce tool restrictions? **Recommendation: Yes, as a follow-up.**
2. **Checkpoint/resume for long workflows**: Save intermediate state to disk so failed runs can resume? **Recommendation: Defer** — sub-agent isolation + increased turns should resolve most premature termination.
3. **Token budget awareness**: Track approximate usage and warn when approaching limits? **Recommendation: Defer** — step-aware continuation addresses the symptom without token counting.
