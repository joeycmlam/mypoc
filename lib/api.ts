import type {
  AgentsResponse,
  HealthResponse,
  StreamAgentParams,
  StreamEvent,
} from "./types";

export async function fetchAgents(): Promise<AgentsResponse> {
  const res = await fetch("/api/agents");
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export function getAgentDisplayName(agentFile: string): string {
  const name = agentFile.replace(/\.agent\.md$|\.md$/, "");
  return name
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function getAgentDescription(agentFile: string): string {
  const name = agentFile.replace(/\.agent\.md$|\.md$/, "").toLowerCase();
  const descriptions: Record<string, string> = {
    assistant: "General-purpose AI assistant",
    ba: "Business analysis and requirements",
    coder: "Code generation and review",
    "e2e-tester": "End-to-end test automation",
    "jira-reader": "Read and summarize Jira issues",
    "jira-test-automator": "Automate Jira test workflows",
    "test-analyst": "Test analysis and planning",
    "test-designer": "Test case design and documentation",
  };
  return descriptions[name] ?? "AI agent";
}

export async function* streamAgent(
  params: StreamAgentParams,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error("Stream request failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data) {
            try {
              yield JSON.parse(data) as StreamEvent;
            } catch {
              // skip malformed SSE data
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
