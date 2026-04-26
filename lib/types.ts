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

export interface AgentMetadata {
  id?: string;
  name?: string;
  description?: string;
  skills?: string[];
  tools?: string[];
  triggers?: string[];
  agents?: string[];
  "argument-hint"?: string;
}

export interface AgentDetail {
  file: string;
  content: string;
  metadata: AgentMetadata;
}

export interface HealthResponse {
  status: string;
  mode?: string;
}
