"use client";

import { X, Bot, Wrench, BookOpen, Zap, ChevronRight, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { fetchAgentContent, getAgentDisplayName } from "@/lib/api";
import type { AgentDetail } from "@/lib/types";

interface AgentContextPanelProps {
  agentFile: string | null;
  onClose: () => void;
}

export function AgentContextPanel({ agentFile, onClose }: AgentContextPanelProps) {
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentFile) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    fetchAgentContent(agentFile)
      .then(setDetail)
      .catch(() => setError("Failed to load agent context."))
      .finally(() => setLoading(false));
  }, [agentFile]);

  const isOpen = agentFile !== null;

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-200",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-full max-w-2xl bg-card border-l border-border shadow-2xl",
          "flex flex-col transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 text-primary">
            <Bot className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-lg truncate">
              {agentFile ? getAgentDisplayName(agentFile) : "Agent Context"}
            </h2>
            <p className="text-xs text-muted-foreground">{agentFile}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
            aria-label="Close panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center h-40 gap-2 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading agent context…</span>
            </div>
          )}

          {error && (
            <div className="m-6 p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}

          {detail && !loading && (
            <div className="divide-y divide-border">
              {/* Metadata section */}
              {(detail.metadata.description ||
                (detail.metadata.skills && detail.metadata.skills.length > 0) ||
                (detail.metadata.tools && detail.metadata.tools.length > 0) ||
                (detail.metadata.triggers && detail.metadata.triggers.length > 0)) && (
                <div className="px-6 py-5 space-y-4">
                  {detail.metadata.description && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                        Description
                      </h3>
                      <p className="text-sm text-foreground leading-relaxed">
                        {detail.metadata.description}
                      </p>
                    </div>
                  )}

                  {detail.metadata.skills && detail.metadata.skills.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                        <BookOpen className="w-3.5 h-3.5" />
                        Skills
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {detail.metadata.skills.map((skill) => (
                          <span
                            key={skill}
                            className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detail.metadata.tools && detail.metadata.tools.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5" />
                        Tools
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {detail.metadata.tools.map((tool) => (
                          <span
                            key={tool}
                            className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          >
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detail.metadata.agents && detail.metadata.agents.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                        <Bot className="w-3.5 h-3.5" />
                        Sub-Agents
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {detail.metadata.agents.map((agent) => (
                          <span
                            key={agent}
                            className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20"
                          >
                            {agent}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detail.metadata.triggers && detail.metadata.triggers.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5" />
                        Triggers
                      </h3>
                      <div className="space-y-1">
                        {detail.metadata.triggers.map((trigger) => (
                          <div
                            key={trigger}
                            className="flex items-center gap-2 text-xs text-muted-foreground"
                          >
                            <ChevronRight className="w-3.5 h-3.5 shrink-0" />
                            <code className="font-mono">{trigger}</code>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* System Prompt section */}
              <div className="px-6 py-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  System Prompt
                </h3>
                <div className="prose-agent text-sm text-foreground leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {detail.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
