"use client";

import { useState, useCallback, useRef } from "react";
import useSWR from "swr";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { MobileSidebar } from "./mobile-sidebar";
import { ChatContainer } from "./chat-container";
import { fetchAgents, checkHealth, streamAgent } from "@/lib/api";
import type { Message, ConnectionStatus, StreamEvent } from "@/lib/types";

function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

export function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("gpt-4o");
  const [maxTurns, setMaxTurns] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [currentTool, setCurrentTool] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { data: agentsData, error: agentsError } = useSWR(
    "agents",
    fetchAgents,
    {
      revalidateOnFocus: false,
    }
  );

  const { data: healthData, error: healthError } = useSWR(
    "health",
    checkHealth,
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
    }
  );

  const connectionStatus: ConnectionStatus =
    healthError || agentsError
      ? "disconnected"
      : healthData
        ? "connected"
        : "connecting";

  const agents = agentsData?.agents || [];

  const handleSend = useCallback(
    async (content: string) => {
      if (!selectedAgent || isLoading) return;

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setCurrentTool(null);

      const assistantMessageId = generateId();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      try {
        abortControllerRef.current = new AbortController();

        const stream = streamAgent({
          agent_file: `agents/${selectedAgent}`,
          instruction: content,
          model: selectedModel,
          max_turns: maxTurns,
        });

        for await (const event of stream) {
          if (abortControllerRef.current?.signal.aborted) break;

          switch (event.type) {
            case "chunk":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: msg.content + (event.content || "") }
                    : msg
                )
              );
              break;

            case "tool":
              setCurrentTool(event.name || null);
              if (event.name) {
                const toolMessage: Message = {
                  id: generateId(),
                  role: "tool",
                  content: `Executing ${event.name}...`,
                  timestamp: new Date(),
                  toolName: event.name,
                };
                setMessages((prev) => [...prev, toolMessage]);
              }
              break;

            case "done":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: event.content || msg.content,
                        isStreaming: false,
                      }
                    : msg
                )
              );
              setCurrentTool(null);
              break;

            case "error":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: `Error: ${event.message}`,
                        isStreaming: false,
                      }
                    : msg
                )
              );
              break;
          }
        }
      } catch (error) {
        console.error("[v0] Stream error:", error);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content:
                    msg.content ||
                    "An error occurred while communicating with the agent.",
                  isStreaming: false,
                }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
        setCurrentTool(null);
        abortControllerRef.current = null;
      }
    },
    [selectedAgent, selectedModel, maxTurns, isLoading]
  );

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
    setCurrentTool(null);
  }, []);

  const handleReset = useCallback(() => {
    setMessages([]);
    setCurrentTool(null);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header
        status={connectionStatus}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        onReset={handleReset}
        isLoading={isLoading}
      />
      <div className="flex-1 flex min-h-0">
        {/* Desktop Sidebar */}
        <div className="hidden lg:block">
          <Sidebar
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            isLoading={isLoading}
            maxTurns={maxTurns}
            onMaxTurnsChange={setMaxTurns}
          />
        </div>
        <main className="flex-1 flex flex-col min-w-0">
          {/* Mobile Sidebar Toggle */}
          <div className="lg:hidden flex items-center gap-2 px-4 py-2 border-b border-border">
            <MobileSidebar
              agents={agents}
              selectedAgent={selectedAgent}
              onSelectAgent={setSelectedAgent}
              isLoading={isLoading}
              maxTurns={maxTurns}
              onMaxTurnsChange={setMaxTurns}
            />
            <span className="text-sm text-muted-foreground">
              {selectedAgent ? `Agent: ${selectedAgent.replace(/\.md$/, "")}` : "Select an agent"}
            </span>
          </div>
          <ChatContainer
            messages={messages}
            onSend={handleSend}
            onStop={handleStop}
            isLoading={isLoading}
            disabled={!selectedAgent || connectionStatus === "disconnected"}
            currentTool={currentTool}
            agentSelected={!!selectedAgent}
          />
        </main>
      </div>
    </div>
  );
}
