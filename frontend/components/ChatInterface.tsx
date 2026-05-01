"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, RotateCcw, Globe, Camera, Cpu, Sparkles,
  Mic, Volume2, VolumeX, Zap,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { v4 as uuidv4 } from "uuid";
import ProductCard from "./ProductCard";
import BudgetOptimizerCard from "./BudgetOptimizerCard";
import ConfidenceMeter from "./ConfidenceMeter";
import { streamChat, resetSession, nextPick, askProduct } from "@/lib/api";
import type {
  ChatMessage,
  ConfidenceBreakdown,
  RecommendationData,
  BudgetPickData,
} from "@/lib/api";

interface JourneyStep { label: string; score: number; }

interface UIMessage extends ChatMessage {
  budgetPick?: BudgetPickData;
  pickNumber?: number;
}

// ── Web Speech API types ────────────────────────────────────────────────────
interface SpeechRecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent extends Event { error: string; }
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror:  ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend:    (() => void) | null;
}

// ── Constants ───────────────────────────────────────────────────────────────
const OPENING_MESSAGE =
  "Tell me what you're looking for — budget, what it's for, anything on your mind. I'll tell you when I'm confident enough to recommend.";

const QUICK_STARTS = [
  { emoji: "👟", label: "Running shoes",  text: "Running shoes for flat feet under ₹5000" },
  { emoji: "🎮", label: "Gaming laptop",  text: "Gaming laptop with RTX GPU and good screen under ₹80000" },
  { emoji: "🚗", label: "Used car",       text: "Used car under 5 lakhs in good condition" },
  { emoji: "💻", label: "Laptop",         text: "Laptop under ₹45000 for college and coding" },
  { emoji: "💄", label: "Skincare",       text: "Skincare for oily skin under ₹1000" },
  { emoji: "🎁", label: "Surprise me",    text: "Surprise me — recommend something useful under ₹3000" },
];

const BUDGET_CHIPS = ["+₹5K", "+₹10K", "+₹20K"];

// ── Status icon helper ───────────────────────────────────────────────────────
function StatusIcon({ text }: { text: string }) {
  const t = text.toLowerCase();
  if (t.includes("opening") || t.includes("browsing")) return <Globe  size={12} className="text-indigo-500 flex-shrink-0" />;
  if (t.includes("reading") || t.includes("section"))  return <Camera size={12} className="text-indigo-500 flex-shrink-0" />;
  if (t.includes("vision")  || t.includes("ranking"))  return <Cpu    size={12} className="text-indigo-500 flex-shrink-0" />;
  return <Zap size={12} className="text-indigo-500 flex-shrink-0" />;
}

// ── Mic Button ──────────────────────────────────────────────────────────────
function MicButton({
  onTranscript,
  onInterim,
  onListeningChange,
  disabled,
}: {
  onTranscript: (text: string) => void;
  onInterim?: (text: string) => void;
  onListeningChange?: (listening: boolean) => void;
  disabled: boolean;
}) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [errorMsg, setErrorMsg]       = useState("");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    setIsSupported(
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)
    );
  }, []);

  const setListening = useCallback((v: boolean) => {
    setIsListening(v);
    onListeningChange?.(v);
  }, [onListeningChange]);

  const startListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      onInterim?.("");
      return;
    }
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SR = ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) as new () => SpeechRecognitionInstance;
      const recognition = new SR();
      recognition.continuous     = false;
      recognition.interimResults = true;
      recognition.lang           = "en-IN";

      recognition.onresult = (e: SpeechRecognitionEvent) => {
        let interim = "";
        let final   = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) final   += t;
          else                       interim += t;
        }
        if (interim) onInterim?.(interim);
        if (final) {
          onInterim?.("");
          onTranscript(final.trim());
        }
      };

      recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
        setListening(false);
        onInterim?.("");
        if (e.error === "not-allowed")  setErrorMsg("Mic access denied — allow microphone in browser settings");
        else if (e.error === "no-speech") setErrorMsg("No speech detected — try again");
        else                              setErrorMsg(`Mic error: ${e.error}`);
        setTimeout(() => setErrorMsg(""), 3500);
      };

      recognition.onend = () => { setListening(false); onInterim?.(""); };

      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [isListening, onTranscript, onInterim, setListening]);

  if (!isSupported) return null;

  return (
    <div className="relative flex flex-col items-center">
      <motion.button
        onClick={startListening}
        disabled={disabled}
        title={isListening ? "Tap to stop" : "Speak your request"}
        whileTap={{ scale: 0.88 }}
        className={`relative p-2.5 rounded-xl transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed overflow-hidden ${
          isListening
            ? "bg-red-500 text-white"
            : "bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
        }`}
      >
        {/* Dual ripple rings */}
        {isListening && (
          <>
            <motion.span
              className="absolute inset-0 rounded-xl bg-red-400"
              animate={{ scale: [1, 1.7], opacity: [0.45, 0] }}
              transition={{ repeat: Infinity, duration: 1.3, ease: "easeOut" }}
            />
            <motion.span
              className="absolute inset-0 rounded-xl bg-red-400"
              animate={{ scale: [1, 1.7], opacity: [0.45, 0] }}
              transition={{ repeat: Infinity, duration: 1.3, ease: "easeOut", delay: 0.45 }}
            />
          </>
        )}

        <span className="relative flex items-center justify-center">
          {isListening ? (
            <span className="flex items-end gap-[2px]" style={{ height: 16 }}>
              {[9, 14, 11, 14, 9].map((h, idx) => (
                <span
                  key={idx}
                  className="wave-bar bg-white rounded-sm"
                  style={{ width: 3, height: h }}
                />
              ))}
            </span>
          ) : (
            <Mic size={16} />
          )}
        </span>
      </motion.button>

      <AnimatePresence>
        {errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="absolute bottom-12 right-0 z-10 w-60 text-xs bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800 px-3 py-2 rounded-lg shadow-lg"
          >
            {errorMsg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Typing dots ─────────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex gap-1 items-center px-1">
      {[0, 160, 320].map(delay => (
        <motion.span
          key={delay}
          className="w-1.5 h-1.5 bg-indigo-400 rounded-full"
          animate={{ y: [0, -5, 0] }}
          transition={{ repeat: Infinity, duration: 0.9, delay: delay / 1000, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export default function ChatInterface() {
  const [messages, setMessages]                   = useState<UIMessage[]>([{ role: "agent", content: OPENING_MESSAGE }]);
  const [input, setInput]                         = useState("");
  const [isStreaming, setIsStreaming]             = useState(false);
  const [sessionId, setSessionId]                 = useState(() => uuidv4());
  const [confidence, setConfidence]               = useState(0);
  const [breakdown, setBreakdown]                 = useState<ConfidenceBreakdown | null>(null);
  const [journey, setJourney]                     = useState<JourneyStep[]>([]);
  const [isStreamingReasoning, setIsStreamingReasoning] = useState(false);
  const [statusText, setStatusText]               = useState("");
  const [celebrated, setCelebrated]               = useState(false);
  const [rejectingIdx, setRejectingIdx]           = useState<number | null>(null);
  const [showBudgetChips, setShowBudgetChips]     = useState(false);
  const [autoSpeak, setAutoSpeak]                 = useState(false);
  const [isListening, setIsListening]             = useState(false);

  const lastBudgetRef   = useRef<number | null>(null);
  const autoSpeakRef    = useRef(false);
  const lastReasoningRef = useRef("");
  const bottomRef       = useRef<HTMLDivElement>(null);
  const inputRef        = useRef<HTMLInputElement>(null);
  const prevConfidence  = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  useEffect(() => {
    if (confidence >= 80 && prevConfidence.current < 80 && !celebrated) {
      setCelebrated(true);
      setShowBudgetChips(true);
    }
    if (confidence < 80) { setCelebrated(false); setShowBudgetChips(false); }
    prevConfidence.current = confidence;
  }, [confidence, celebrated]);

  const toggleAutoSpeak = useCallback(() => {
    setAutoSpeak(v => {
      const next = !v;
      autoSpeakRef.current = next;
      if (!next && typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      return next;
    });
  }, []);

  const hasUserMessages = messages.some(m => m.role === "user");

  const addAgentMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: "agent", content, type: "text" }]);
  }, []);

  const addRecommendation = useCallback((data: RecommendationData, pickNumber = 1) => {
    setMessages(prev => [...prev, {
      role: "agent", content: "", type: "recommendation",
      recommendation: data, pickNumber,
    }]);
  }, []);

  // ── "Not this one" ─────────────────────────────────────────────────────────
  const handleReject = useCallback(async (msgIndex: number) => {
    setRejectingIdx(msgIndex);
    try {
      const result = await nextPick(sessionId);
      if (result.error || !result.product) {
        addAgentMessage(result.message || "No more alternatives — try describing your needs differently.");
        return;
      }
      const pickNum = result.pick_number ?? 2;
      setMessages(prev => [...prev, {
        role: "agent", content: "", type: "recommendation",
        recommendation: {
          product: result.product!,
          reasoning: `Pick #${pickNum} — next-best match for your stated needs.`,
          regret_risk: "medium",
          regret_scenario: "",
          tradeoff: "Slightly lower match score than the top pick.",
          confidence_score: result.confidence_score ?? 0,
          elimination: [],
        },
        pickNumber: pickNum,
      }]);
    } catch {
      addAgentMessage("Couldn't fetch the next pick. Please try again.");
    } finally {
      setRejectingIdx(null);
    }
  }, [sessionId, addAgentMessage]);

  // ── "Ask anything" ─────────────────────────────────────────────────────────
  const handleAsk = useCallback(async (question: string): Promise<string> => {
    return askProduct(sessionId, question);
  }, [sessionId]);

  // ── Budget chip ────────────────────────────────────────────────────────────
  const handleBudgetChip = useCallback((chip: string) => {
    const match = chip.match(/\+₹(\d+)K/);
    if (!match) return;
    const newBudget = (lastBudgetRef.current ?? 0) + parseInt(match[1]) * 1000;
    lastBudgetRef.current = newBudget;
    handleSend(`Increase my budget to ₹${newBudget.toLocaleString("en-IN")}`);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Main send ─────────────────────────────────────────────────────────────
  const handleSend = useCallback(async (override?: string) => {
    const trimmed = (override ?? input).trim();
    if (!trimmed || isStreaming) return;

    const budgetMatch = trimmed.match(/₹\s*([\d,]+)/);
    if (budgetMatch) {
      const num = parseInt(budgetMatch[1].replace(/,/g, ""));
      if (!isNaN(num)) lastBudgetRef.current = num;
    }

    setMessages(prev => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsStreaming(true);
    setStatusText("");
    setShowBudgetChips(false);
    lastReasoningRef.current = "";

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
            if (event.content) { setStatusText(""); addAgentMessage(event.content); }
            break;

          case "followup":
            if (event.question) {
              setStatusText("");
              addAgentMessage(event.question);
              stepLabel = "Follow-up answered";
            }
            break;

          case "budget_pick":
            if (event.product && event.savings !== undefined && event.fit_pct !== undefined) {
              setMessages(prev => [...prev, {
                role: "agent", content: "", type: "text",
                budgetPick: {
                  product: event.product!,
                  savings: event.savings!,
                  fit_pct: event.fit_pct!,
                  confidence_score: event.confidence_score ?? 0,
                },
              }]);
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
              lastReasoningRef.current = "";
              setMessages(prev => [...prev, {
                role: "agent", content: "", type: "recommendation", pickNumber: 1,
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
              lastReasoningRef.current += event.text;
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
                      regret_risk:     event.regret_risk     || "low",
                      regret_scenario: event.regret_scenario || "",
                      tradeoff:        event.tradeoff        || "",
                    },
                  };
                  break;
                }
              }
              return updated;
            });
            // ── Auto-TTS ──────────────────────────────────────────────────
            if (autoSpeakRef.current && lastReasoningRef.current && typeof window !== "undefined" && "speechSynthesis" in window) {
              const textToSpeak = lastReasoningRef.current;
              setTimeout(() => {
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance(textToSpeak);
                utter.lang  = "en-IN";
                utter.rate  = 0.88;
                utter.pitch = 1.0;
                window.speechSynthesis.speak(utter);
              }, 400);
            }
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

  const handleVoiceTranscript = useCallback((text: string) => {
    setInput(text);
    setTimeout(() => handleSend(text), 600);
  }, [handleSend]);

  const handleVoiceInterim = useCallback((text: string) => {
    setInput(text);
  }, []);

  const handleReset = useCallback(async () => {
    const newId = uuidv4();
    await resetSession(sessionId);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setSessionId(newId);
    setMessages([{ role: "agent", content: OPENING_MESSAGE }]);
    setConfidence(0);
    setBreakdown(null);
    setJourney([]);
    setInput("");
    setStatusText("");
    setIsStreamingReasoning(false);
    setCelebrated(false);
    setShowBudgetChips(false);
    lastBudgetRef.current    = null;
    lastReasoningRef.current = "";
    inputRef.current?.focus();
  }, [sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-white dark:bg-gray-950 overflow-hidden">

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="hidden md:flex w-56 flex-col border-r border-gray-100 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm p-4 gap-6 overflow-y-auto">
        <div className="pt-1">
          <span className="text-base font-semibold tracking-tight text-gray-900 dark:text-white">
            Shop<span className="text-indigo-600">Sense</span>
          </span>
          <p className="text-xs text-gray-400 mt-0.5">AI Shopping Agent</p>
        </div>

        <ConfidenceMeter score={confidence} breakdown={breakdown} journey={journey} celebrated={celebrated} />

        {/* Auto-speak toggle */}
        <motion.button
          onClick={toggleAutoSpeak}
          whileTap={{ scale: 0.96 }}
          title={autoSpeak ? "Auto-read ON — click to mute" : "Auto-read recommendations aloud"}
          className={`flex items-center gap-2 text-xs rounded-lg px-2.5 py-2 transition-all border ${
            autoSpeak
              ? "bg-violet-50 dark:bg-violet-950/60 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300"
              : "border-gray-200 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 bg-white dark:bg-gray-900"
          }`}
        >
          {autoSpeak ? <Volume2 size={12} /> : <VolumeX size={12} />}
          <span>{autoSpeak ? "Reading aloud" : "Read aloud"}</span>
          {autoSpeak && (
            <motion.span
              animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
              transition={{ repeat: Infinity, duration: 1.4 }}
              className="ml-auto w-1.5 h-1.5 rounded-full bg-violet-500"
            />
          )}
        </motion.button>

        <button
          onClick={handleReset}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors mt-auto"
        >
          <RotateCcw size={12} />
          Start over
        </button>
      </aside>

      {/* ── Main chat ────────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 relative">

        {/* Ambient background */}
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
            <button onClick={toggleAutoSpeak} className="text-gray-400">
              {autoSpeak ? <Volume2 size={14} className="text-violet-500" /> : <VolumeX size={14} />}
            </button>
            <button onClick={handleReset}><RotateCcw size={14} className="text-gray-400" /></button>
          </div>
        </div>

        {/* Messages */}
        <div className="relative flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.28, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                {/* Avatar */}
                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                  msg.role === "agent"
                    ? "bg-indigo-100 dark:bg-indigo-900 text-indigo-600 dark:text-indigo-300"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
                }`}>
                  {msg.role === "agent"
                    ? <Sparkles size={13} />
                    : <span className="text-[11px] font-bold">U</span>}
                </div>

                <div className={`max-w-[80%] ${msg.role === "user" ? "items-end flex flex-col" : ""}`}>
                  {/* Budget optimizer card */}
                  {msg.budgetPick ? (
                    <div className="w-full max-w-md">
                      <BudgetOptimizerCard data={msg.budgetPick} />
                    </div>

                  /* Product recommendation card */
                  ) : msg.type === "recommendation" && msg.recommendation ? (
                    <div className="w-full max-w-md">
                      <ProductCard
                        data={msg.recommendation}
                        isStreaming={isStreamingReasoning && i === messages.length - 1}
                        pickNumber={msg.pickNumber ?? 1}
                        onReject={i === messages.length - 1 ? () => handleReject(i) : undefined}
                        isRejecting={rejectingIdx === i}
                        onAsk={handleAsk}
                      />
                    </div>

                  /* Text bubble */
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

          {/* Live status / thinking indicator */}
          <AnimatePresence>
            {isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22 }}
                className="flex gap-2.5 items-center"
              >
                {/* Spinning avatar */}
                <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center flex-shrink-0">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1.6, ease: "linear" }}
                  >
                    <Sparkles size={12} className="text-indigo-600" />
                  </motion.div>
                </div>

                <div className="flex items-center gap-2 px-3.5 py-2.5 bg-white dark:bg-gray-800 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100 dark:border-gray-700 min-w-0">
                  <AnimatePresence mode="wait">
                    {statusText ? (
                      <motion.div
                        key={statusText}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 8 }}
                        transition={{ duration: 0.18 }}
                        className="flex items-center gap-1.5"
                      >
                        <StatusIcon text={statusText} />
                        <span className="text-xs text-gray-600 dark:text-gray-400 truncate">{statusText}</span>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="dots"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                      >
                        <TypingDots />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={bottomRef} />
        </div>

        {/* ── Input area ─────────────────────────────────────────────────── */}
        <div className="relative border-t border-gray-100 dark:border-gray-800 bg-white/80 dark:bg-gray-950/80 backdrop-blur-sm px-4 py-3">

          {/* Quick-start chips */}
          <AnimatePresence>
            {!hasUserMessages && !isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="flex flex-wrap gap-2 mb-3"
              >
                {QUICK_STARTS.map((chip, i) => (
                  <motion.button
                    key={chip.label}
                    initial={{ opacity: 0, scale: 0.88, y: 6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ delay: i * 0.065, type: "spring", stiffness: 380, damping: 22 }}
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

          {/* Budget adjustment chips */}
          <AnimatePresence>
            {showBudgetChips && !isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="flex items-center gap-2 mb-3"
              >
                <span className="text-xs text-gray-400">Stretch budget?</span>
                {BUDGET_CHIPS.map((chip, i) => (
                  <motion.button
                    key={chip}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.07 }}
                    onClick={() => handleBudgetChip(chip)}
                    className="text-xs px-2.5 py-1 rounded-full border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900 transition-all active:scale-95"
                  >
                    {chip}
                  </motion.button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Input row */}
          <div className="flex gap-2 items-center">
            <div className="relative flex-1">
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isStreaming}
                placeholder={isListening ? "Listening…" : "Tell me what you're looking for… or tap the mic 🎤"}
                className={`w-full text-sm px-3.5 py-2.5 rounded-xl border bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:border-transparent disabled:opacity-50 transition-all shadow-sm ${
                  isListening
                    ? "border-red-400 ring-2 ring-red-200 dark:ring-red-900 focus:ring-red-300"
                    : "border-gray-200 dark:border-gray-700 focus:ring-indigo-500"
                }`}
              />
              {/* Inline waveform while listening */}
              <AnimatePresence>
                {isListening && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 flex items-end gap-[2px]"
                    style={{ height: 16 }}
                  >
                    {[7, 12, 9, 12, 7].map((h, idx) => (
                      <span
                        key={idx}
                        className="wave-bar bg-red-400 rounded-sm"
                        style={{ width: 2, height: h }}
                      />
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <MicButton
              onTranscript={handleVoiceTranscript}
              onInterim={handleVoiceInterim}
              onListeningChange={setIsListening}
              disabled={isStreaming}
            />

            <motion.button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming}
              whileTap={{ scale: 0.9 }}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all shadow-sm"
            >
              <Send size={16} />
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  );
}
