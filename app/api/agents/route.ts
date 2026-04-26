import { NextResponse } from "next/server";

const MOCK_AGENTS = [
  "assistant.md",
  "ba.agent.md",
  "coder.md",
  "e2e-tester.md",
  "jira-reader.md",
  "jira-test-automator.agent.md",
  "test-analyst.agent.md",
  "test-designer.md",
];

export async function GET() {
  // Try to reach the Python backend, fallback to mock if unavailable
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/agents`, {
      next: { revalidate: 0 },
    });
    if (response.ok) {
      const data = await response.json();
      // Normalize: backend may return {agents: [...objects], files: [...strings]}
      // Prefer `files` (plain filenames) when present; otherwise ensure agents are strings.
      const agents: string[] = Array.isArray(data.files)
        ? data.files
        : (data.agents as unknown[]).map((a) =>
            typeof a === "string" ? a : (a as { id: string }).id
          );
      return NextResponse.json({ agents });
    }
  } catch {
    // Backend not available, return mock response
  }

  return NextResponse.json({ agents: MOCK_AGENTS });
}
