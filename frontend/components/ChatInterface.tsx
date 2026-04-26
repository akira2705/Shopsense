"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Globe, Camera, Cpu, Sparkles, Mic, MicOff } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { v4 as uuidv4 } from "uuid";
import ProductCard from "./ProductCard";
import ConfidenceMeter from "./ConfidenceMeter";
import { streamChat, resetSession } from "@/lib/api";
import type { ChatMessage, ConfidenceBreakdown, RecommendationData } from "@/lib/api";

interface JourneyStep {
  label: string;
  score: number;
}

// Web Speech API type declarations
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}
declare const SpeechRecognition: new () => SpeechRecognitionInstance;
declare const webkitSpeechRecognition: new () => SpeechRecognitionInstance;

const OPENING_MESSAGE =
  "Tell me what you're looking for — budget, what it's for, anything on your mind. I'll tell you when I'm confident enough to recommend.";

const QUICK_STARTS = [
  { emoji: "👟", label: "Running shoes", text: "Running shoes for flat feet under ₹5000" },
  { emoji: "📱", label: "Smartphone",    text: "Smartphone under ₹15000 for photography" },
  { emoji: "🚗", label: "Used car",      text: "Used car under 5 lakhs in good condition" },
  { emoji: "💻", label: "Laptop",        text: "Laptop under ₹45000 for college and coding" },
  { emoji: "💄", label: "Skincare",      text: "Skincare for oily skin under ₹1000" },
];

// Map status text → icon
function StatusIcon({ text }: { text: string }) {
  const t = text.toLowerCase();
  if (t.includes("opening") || t.includes("browsing"))  return <Globe size={12} className="text-indigo-500 animate-pulse" />;
  if (t.includes("screenshot") || t.includes("reading")) return <Camera size={12} className="text-indigo-500 animate-pulse" />;
  return <Cpu size={12} className="text-indigo-500 animate-pulse" />;
}

// Mic button with recording state
function MicButton({ onTranscript, disabled }: { onTranscript: (text: string) => void; disabled: boolean }) {
  const [isListening, setIsListening]     = useState(false);
  const [isSupported, setIsSupported]     = useState(false);
  const [errorMsg, setErrorMsg]           = useState("");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    const supported = typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setIsSupported(supported);
  }, []);

  const startListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SR = ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) as new () => SpeechRecognitionInstance;
      const recognition = new SR();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-IN";

      recognition.onresult = (e: SpeechRecognitionEvent) => {
        const transcript = Array.from(e.results)
          .map(r => r[0].transcript)
          .join(" ")
          .trim();
        if (transcript) onTranscript(transcript);
      };

      recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
        setIsListening(false);
        if (e.error === "not-allowed") setErrorMsg("Mic access denied — allow microphone in browser settings");
        else if (e.error === "no-speech") setErrorMsg("No speech detected — try again");
        else setErrorMsg(`Mic error: ${e.error}`);
        setTimeout(() => setErrorMsg(""), 3500);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
      setIsListening(true);
    } catch {
      setIsListening(false);
    }
  }, [isListening, onTranscript]);

  if (!isSupported) return null;

  return (
    <div className="relative flex flex-col items-center">
      <motion.button
        onClick={startListening}
        disabled={disabled}
        title={isListening ? "Tap to stop" : "Speak your request"}
        whileTap={{ scale: 0.92 }}
        className={`relative p-2.5 rounded-xl transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed ${
          isListening
            ? "bg-red-500 hover:bg-red-600 text-white"
            : "bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
        }`}
      >
        {/* Pulse ring when recording */}
        {isListening && (
          <motion.span
            className="absolute inset-0 rounded-xl bg-red-400"
            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
          />
        )}
        <span className="relative">
          {isListening ? <MicOff size={16} /> : <Mic size={16} />}
        </span>
      </motion.button>

      {/* Error tooltip */}
      <AnimatePresence>
        {errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="absolute bottom-12 right-0 z-10 w-56 text-xs bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800 px-3 py-2 rounded-lg shadow-md"
          >
            {errorMsg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function ChatInterface() {
  const [messages, setMessages]             = useState<ChatMessage[]>([{ role: "agent", content: OPENING_MESSAGE }]);
  const [input, setInput]                   = useState("");
  const [isStreaming, setIsStreaming]        = useState(false);
  const [sessionId, setSessionId]           = useState(() => uuidv4());
  const [confidence, setConfidence]         = useState(0);
  const [breakdown, setBreakdown]           = useState<ConfidenceBreakdown | null>(null);
  const [journey, setJourney]               = useState<JourneyStep[]>([]);
  const [isStreamingReasoning, setIsStreamingReasoning] = useState(false);
  const [statusText, setStatusText]         = useState("");
  const [celebrated, setCelebrated]         = useState(false);

  const bottomRef  = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLInputElement>(null);
  const prevConfidence = useRef(0);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  // Celebrate when confidence first crosses 80
  useEffect(() => {
    if (confidence >= 80 && prevConfidence.current < 80 && !celebrated) {
      setCelebrated(true);
    }
    if (confidence < 80) setCelebrated(false);
    prevConfidence.current = confidence;
  }, [confidence, celebrated]);

  const hasUserMessages = messages.some(m => m.role === "user");

  const addAgentMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: "agent", content, type: "text" }]);
  }, []);

  const addRecommendation = useCallback((data: RecommendationData) => {
    setMessages(prev => [...prev, { role: "agent", content: "", type: "recommendation", recommendation: data }]);
  }, []);

  const handleSend = useCallback(async (override?: string) => {
    const trimmed = (override ?? input).trim();
    if (!trimmed || isStreaming) return;

    setMessages(prev => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsStreaming(true);
    setStatusText("");

    try {
      const historyForApi = [...messages, { role: "user" as const, content: trimmed }];
      let stepLabel = trimmed.slice(0, 28) + (trimmed.length > 28 ? "…" : "");

      for await (const event of streamChat(trimmed, sessionId, historyForApi)) {
        switch (event.type) {

          case "confidence":
            if (event.score !== undefined) {
              setConfidence(event.score);
              if (event.breakdown) setBreakdown(event.breakdown);
              if (event.session_id) setSessionId(event.session_id);
              setJourney(prev => {
                const last = prev[prev.length - 1];
                if (last && last.score === event.score) return prev;
                return [...prev, { label: stepLabel, score: event.score! }];
              });
            }
            break;

          case "status":
            if (event.text) setStatusText(event.text);
            break;

          case "message":
            if (event.content) {
              setStatusText("");
              addAgentMessage(event.content);
            }
            break;

          case "followup":
            if (event.question) {
              setStatusText("");
              addAgentMessage(event.question);
              stepLabel = "Follow-up answered";
            }
            break;

          case "recommendation":
            if (event.product) {
              setStatusText("");
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

          case "recommendation_start":
            if (event.product) {
              setStatusText("");
              setIsStreamingReasoning(true);
              setMessages(prev => [...prev, {
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
              }]);
            }
            break;

          case "token":
            if (event.text) {
              setMessages(prev => {
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

          case "recommendation_done":
            setIsStreamingReasoning(false);
            setMessages(prev => {
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
            setStatusText("");
            addAgentMessage(event.message || "Something went wrong. Please try again.");
            break;

          case "done":
            setStatusText("");
            break;
        }
      }
    } catch {
      addAgentMessage("I had trouble connecting. Please check your connection and try again.");
    } finally {
      setIsStreaming(false);
      setStatusText("");
      inputRef.current?.focus();
    }
  }, [input, isStreaming, sessionId, messages, confidence, addAgentMessage, addRecommendation]);

  // Voice transcript handler — fill input then auto-send
  const handleVoiceTranscript = useCallback((text: string) => {
    setInput(text);
    // Small delay so user sees what was transcribed before it sends
    setTimeout(() => {
      handleSend(text);
    }, 600);
  }, [handleSend]);

  const handleReset = useCallback(async () => {
    const newId = uuidv4();
    await resetSession(sessionId);
    setSessionId(newId);
    setMessages([{ role: "agent", content: OPENING_MESSAGE }]);
    setConfidence(0);
    setBreakdown(null);
    setJourney([]);
    setInput("");
    setStatusText("");
    setIsStreamingReasoning(false);
    setCelebrated(false);
    inputRef.current?.focus();
  }, [sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950 overflow-hidden">

      {/* Sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm p-4 gap-6 overflow-y-auto">
        <div className="pt-1">
          <span className="text-base font-semibold tracking-tight text-gray-900 dark:text-white">
            Shop<span className="text-indigo-600">Sense</span>
          </span>
          <p className="text-xs text-gray-400 mt-0.5">AI Shopping Agent</p>
        </div>

        <ConfidenceMeter score={confidence} breakdown={breakdown} journey={journey} celebrated={celebrated} />

        <button
          onClick={handleReset}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors mt-auto"
        >
          <RotateCcw size={12} />
          Start over
        </button>
      </aside>

      {/* Main chat */}
      <div className="flex flex-col flex-1 min-w-0 relative">

        {/* Subtle gradient background */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-indigo-50/40 via-white to-white dark:from-indigo-950/20 dark:via-gray-950 dark:to-gray-950" />

        {/* Mobile header */}
        <div className="relative flex md:hidden items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800 bg-white/80 dark:bg-gray-950/80 backdrop-blur-sm">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            Shop<span className="text-indigo-600">Sense</span>
          </span>
          <div className="flex items-center gap-3">
            <motion.span
              key={confidence}
              initial={{ scale: 0.85 }}
              animate={{ scale: 1 }}
              className={`text-xs font-semibold transition-colors ${confidence >= 80 ? "text-green-600" : "text-indigo-600"}`}
            >
              {confidence}% confident
            </motion.span>
            <button onClick={handleReset}><RotateCcw size={14} className="text-gray-400" /></button>
          </div>
        </div>

        {/* Messages */}
        <div className="relative flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                {/* Avatar */}
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5 ${
                  msg.role === "agent"
                    ? "bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                }`}>
                  {msg.role === "agent" ? "S" : "U"}
                </div>

                <div className={`max-w-[80%] ${msg.role === "user" ? "items-end flex flex-col" : ""}`}>
                  {msg.type === "recommendation" && msg.recommendation ? (
                    <div className="w-full max-w-md">
                      <ProductCard
                        data={msg.recommendation}
                        isStreaming={isStreamingReasoning && i === messages.length - 1}
                      />
                    </div>
                  ) : msg.content ? (
                    <div className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white rounded-tr-sm shadow-sm"
                        : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm shadow-sm border border-gray-100 dark:border-gray-700"
                    }`}>
                      {msg.content}
                    </div>
                  ) : null}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Live browser status indicator */}
          <AnimatePresence>
            {isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
                className="flex gap-2.5 items-center"
              >
                <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center flex-shrink-0">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                  >
                    <Sparkles size={12} className="text-indigo-600" />
                  </motion.div>
                </div>

                <div className="flex items-center gap-2 px-3.5 py-2.5 bg-white dark:bg-gray-800 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100 dark:border-gray-700 min-w-0">
                  {statusText ? (
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={statusText}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 6 }}
                        transition={{ duration: 0.18 }}
                        className="flex items-center gap-1.5"
                      >
                        <StatusIcon text={statusText} />
                        <span className="text-xs text-gray-600 dark:text-gray-400 truncate">{statusText}</span>
                      </motion.div>
                    </AnimatePresence>
                  ) : (
                    <div className="flex gap-1 items-center">
                      {[0, 150, 300].map(delay => (
                        <span
                          key={delay}
                          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: `${delay}ms` }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="relative border-t border-gray-100 dark:border-gray-800 bg-white/80 dark:bg-gray-950/80 backdrop-blur-sm px-4 py-3">

          {/* Quick-start chips — only on first load */}
          <AnimatePresence>
            {!hasUserMessages && !isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ duration: 0.25 }}
                className="flex flex-wrap gap-2 mb-3"
              >
                {QUICK_STARTS.map((chip, i) => (
                  <motion.button
                    key={chip.label}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.06, duration: 0.2 }}
                    onClick={() => handleSend(chip.text)}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:border-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950 hover:text-indigo-700 text-gray-600 dark:text-gray-400 transition-all active:scale-95 shadow-sm"
                  >
                    <span>{chip.emoji}</span>
                    {chip.label}
                  </motion.button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex gap-2 items-center">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Tell me what you're looking for… or tap the mic 🎤"
              className="flex-1 text-sm px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50 transition shadow-sm"
            />

            {/* Voice input button */}
            <MicButton onTranscript={handleVoiceTranscript} disabled={isStreaming} />

            {/* Send button */}
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all shadow-sm"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
