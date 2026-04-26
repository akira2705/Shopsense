"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { v4 as uuidv4 } from "uuid";
import ProductCard from "./ProductCard";
import ConfidenceMeter from "./ConfidenceMeter";
import { streamChat, resetSession } from "@/lib/api";
import type {
  ChatMessage,
  ConfidenceBreakdown,
  RecommendationData,
} from "@/lib/api";

interface JourneyStep {
  label: string;
  score: number;
}

const OPENING_MESSAGE =
  "Tell me what you're looking for — budget, what it's for, anything on your mind. I'll tell you when I'm confident enough to recommend.";

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", content: OPENING_MESSAGE },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(() => uuidv4());

  const [confidence, setConfidence] = useState(0);
  const [breakdown, setBreakdown] = useState<ConfidenceBreakdown | null>(null);
  const [journey, setJourney] = useState<JourneyStep[]>([]);
  const [isStreamingReasoning, setIsStreamingReasoning] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addAgentMessage = useCallback((content: string) => {
    setMessages((prev) => [...prev, { role: "agent", content, type: "text" }]);
  }, []);

  const addRecommendation = useCallback((data: RecommendationData) => {
    setMessages((prev) => [
      ...prev,
      { role: "agent", content: "", type: "recommendation", recommendation: data },
    ]);
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const userMsg: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    try {
      const historyForApi = [...messages, userMsg];
      let stepLabel = trimmed.slice(0, 28) + (trimmed.length > 28 ? "…" : "");

      for await (const event of streamChat(trimmed, sessionId, historyForApi)) {
        switch (event.type) {
          case "confidence":
            if (event.score !== undefined) {
              setConfidence(event.score);
              if (event.breakdown) setBreakdown(event.breakdown);
              // Update session ID from first event
              if (event.session_id) setSessionId(event.session_id);
              // Add journey step
              setJourney((prev) => {
                const last = prev[prev.length - 1];
                if (last && last.score === event.score) return prev;
                return [...prev, { label: stepLabel, score: event.score! }];
              });
            }
            break;

          case "message":
            if (event.content) addAgentMessage(event.content);
            break;

          case "followup":
            if (event.question) {
              addAgentMessage(event.question);
              stepLabel = "Follow-up answered";
            }
            break;

          // legacy recommendation event (fallback)
          case "recommendation":
            if (event.product) {
              addRecommendation({
                product: event.product,
                reasoning: event.reasoning || "",
                regret_risk: event.regret_risk || "low",
                regret_scenario: event.regret_scenario || "",
                tradeoff: event.tradeoff || "",
                confidence_score: event.confidence_score || confidence,
                elimination: event.elimination || [],
              });
            }
            break;

          // A: streaming recommendation — step 1: product card with empty reasoning
          case "recommendation_start":
            if (event.product) {
              setIsStreamingReasoning(true);
              setMessages((prev) => [
                ...prev,
                {
                  role: "agent",
                  content: "",
                  type: "recommendation",
                  recommendation: {
                    product: event.product!,
                    reasoning: "",
                    regret_risk: "low",
                    regret_scenario: "",
                    tradeoff: "",
                    confidence_score: event.confidence_score || confidence,
                    elimination: event.elimination || [],
                  },
                },
              ]);
            }
            break;

          // A: streaming reasoning token — append to last recommendation
          case "token":
            if (event.text) {
              setMessages((prev) => {
                const updated = [...prev];
                for (let i = updated.length - 1; i >= 0; i--) {
                  if (updated[i].type === "recommendation" && updated[i].recommendation) {
                    updated[i] = {
                      ...updated[i],
                      recommendation: {
                        ...updated[i].recommendation!,
                        reasoning: updated[i].recommendation!.reasoning + event.text,
                      },
                    };
                    break;
                  }
                }
                return updated;
              });
            }
            break;

          // A: streaming done — patch in regret_risk / tradeoff
          case "recommendation_done":
            setIsStreamingReasoning(false);
            setMessages((prev) => {
              const updated = [...prev];
              for (let i = updated.length - 1; i >= 0; i--) {
                if (updated[i].type === "recommendation" && updated[i].recommendation) {
                  updated[i] = {
                    ...updated[i],
                    recommendation: {
                      ...updated[i].recommendation!,
                      regret_risk: event.regret_risk || "low",
                      regret_scenario: event.regret_scenario || "",
                      tradeoff: event.tradeoff || "",
                    },
                  };
                  break;
                }
              }
              return updated;
            });
            break;

          case "error":
            addAgentMessage(
              event.message || "Something went wrong. Please try again."
            );
            break;

          case "done":
            break;
        }
      }
    } catch (err) {
      addAgentMessage(
        "I had trouble connecting. Please check your connection and try again."
      );
    } finally {
      setIsStreaming(false);
      inputRef.current?.focus();
    }
  }, [input, isStreaming, sessionId, messages, confidence, addAgentMessage, addRecommendation]);

  const handleReset = useCallback(async () => {
    const newId = uuidv4();
    await resetSession(sessionId);
    setSessionId(newId);
    setMessages([{ role: "agent", content: OPENING_MESSAGE }]);
    setConfidence(0);
    setBreakdown(null);
    setJourney([]);
    setInput("");
    setIsStreamingReasoning(false);
    inputRef.current?.focus();
  }, [sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950">
      {/* Sidebar — confidence panel */}
      <aside className="hidden md:flex w-56 flex-col border-r border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-4 gap-6 overflow-y-auto">
        {/* Logo */}
        <div className="pt-1">
          <span className="text-base font-semibold tracking-tight text-gray-900 dark:text-white">
            Shop<span className="text-indigo-600">Sense</span>
          </span>
          <p className="text-xs text-gray-400 mt-0.5">AI Shopping Agent</p>
        </div>

        <ConfidenceMeter
          score={confidence}
          breakdown={breakdown}
          journey={journey}
        />

        {/* Reset button */}
        <button
          onClick={handleReset}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors mt-auto"
        >
          <RotateCcw size={12} />
          Start over
        </button>
      </aside>

      {/* Main chat */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Mobile header */}
        <div className="flex md:hidden items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            Shop<span className="text-indigo-600">Sense</span>
          </span>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-indigo-600">
              {confidence}% confident
            </span>
            <button onClick={handleReset}>
              <RotateCcw size={14} className="text-gray-400" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5 ${
                    msg.role === "agent"
                      ? "bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                  }`}
                >
                  {msg.role === "agent" ? "S" : "U"}
                </div>

                {/* Bubble / card */}
                <div className={`max-w-[80%] ${msg.role === "user" ? "items-end flex flex-col" : ""}`}>
                  {msg.type === "recommendation" && msg.recommendation ? (
                    <div className="w-full max-w-md">
                      <ProductCard
                        data={msg.recommendation}
                        isStreaming={isStreamingReasoning && i === messages.length - 1}
                      />
                    </div>
                  ) : msg.content ? (
                    <div
                      className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-indigo-600 text-white rounded-tr-sm"
                          : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm"
                      }`}
                    >
                      {msg.content}
                    </div>
                  ) : null}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Streaming indicator */}
          {isStreaming && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-2.5 items-center"
            >
              <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center">
                <Loader2 size={12} className="text-indigo-600 animate-spin" />
              </div>
              <div className="flex gap-1 items-center px-3.5 py-2.5 bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-tl-sm">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-3">
          <div className="flex gap-2 items-center">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Tell me what you're looking for..."
              className="flex-1 text-sm px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50 transition"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
