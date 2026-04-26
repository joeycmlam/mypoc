export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  toolName?: string;
}

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export interface StreamEvent {
  type: "chunk" | "tool" | "done" | "error";
  content?: string;
  name?: string;
  message?: string;
}

export interface StreamAgentParams {
  agent_file: string;
  instruction: string;
  model: string;
  max_turns: number;
}

export interface AgentsResponse {
  agents: string[];
}

export interface HealthResponse {
  status: string;
  mode?: string;
}
