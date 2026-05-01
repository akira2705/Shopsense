"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  ExternalLink, AlertCircle, TrendingUp, Star,
  ShoppingCart, X, Volume2, Share2, MessageCircle,
  Send, ChevronDown,
} from "lucide-react";
import Image from "next/image";
import { useState, useRef } from "react";
import EliminationPanel from "./EliminationPanel";
import type { RecommendationData } from "@/lib/api";

interface Props {
  data: RecommendationData;
  isStreaming?: boolean;
  onReject?: () => void;
  isRejecting?: boolean;
  pickNumber?: number;           // 1 = top pick, 2+ = alternate
  sessionId?: string;
  onAsk?: (question: string) => Promise<string>;
}

const REGRET_CONFIG = {
  low: {
    label: "Low regret risk",
    bg: "bg-green-50 dark:bg-green-950",
    text: "text-green-700 dark:text-green-400",
    dot: "bg-green-500",
  },
  medium: {
    label: "Medium regret risk",
    bg: "bg-amber-50 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  high: {
    label: "High regret risk",
    bg: "bg-red-50 dark:bg-red-950",
    text: "text-red-700 dark:text-red-400",
    dot: "bg-red-500",
  },
};

const SHOPIFY_STORE = "shopsense-rueprzpz.myshopify.com";

const SOURCE_LABELS: Record<string, string> = {
  amazon:   "Amazon.in",
  flipkart: "Flipkart",
  carwale:  "CarWale",
  olx:      "OLX",
  shopify:  "Store",
};

const SOURCE_SEARCH_URLS: Record<string, string> = {
  amazon:   "https://www.amazon.in/s?k=",
  flipkart: "https://www.flipkart.com/search?q=",
  carwale:  "https://www.carwale.com/search/?q=",
  olx:      "https://www.olx.in/items/q-",
};

export default function ProductCard({
  data,
  isStreaming = false,
  onReject,
  isRejecting = false,
  pickNumber = 1,
  onAsk,
}: Props) {
  const { product, reasoning, regret_risk, regret_scenario, tradeoff, confidence_score, elimination } = data;
  const regret = REGRET_CONFIG[regret_risk] || REGRET_CONFIG.low;
  const [imgFailed, setImgFailed]   = useState(false);
  const [imgLoaded, setImgLoaded]   = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [copied, setCopied]         = useState(false);
  const [askOpen, setAskOpen]       = useState(false);
  const [askInput, setAskInput]     = useState("");
  const [askAnswer, setAskAnswer]   = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const askRef = useRef<HTMLInputElement>(null);

  const sourceKey = product.source || "shopify";
  const sourceLabel = SOURCE_LABELS[sourceKey] || sourceKey;
  const isShopify = sourceKey === "shopify" || !product.source;

  // Build view URL
  const sourceUrl = product.url
    || (SOURCE_SEARCH_URLS[sourceKey]
        ? SOURCE_SEARCH_URLS[sourceKey] + encodeURIComponent(product.title)
        : `https://${SHOPIFY_STORE}/products/${product.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);

  // Build Shopify cart URL from variant_id GID
  const cartUrl = (() => {
    if (!isShopify || !product.variant_id) return null;
    const numeric = product.variant_id.split("/").pop();
    if (!numeric || isNaN(Number(numeric))) return null;
    return `https://${SHOPIFY_STORE}/cart/${numeric}:1`;
  })();

  // ── TTS ────────────────────────────────────────────────────────────────────
  const handleSpeak = () => {
    if (!("speechSynthesis" in window)) return;
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }
    const text = [
      `${product.title}. Price: ₹${product.price.toLocaleString("en-IN")}.`,
      reasoning,
      tradeoff ? `One tradeoff: ${tradeoff}` : "",
    ].filter(Boolean).join(" ");

    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-IN";
    utter.rate = 0.95;
    utter.onend = () => setIsSpeaking(false);
    utter.onerror = () => setIsSpeaking(false);
    setIsSpeaking(true);
    window.speechSynthesis.speak(utter);
  };

  // ── Share / Copy ───────────────────────────────────────────────────────────
  const handleShare = async () => {
    const text = `🛒 ShopSense recommends: ${product.title}\n💰 ₹${product.price.toLocaleString("en-IN")}\n\n${reasoning}\n\n🔗 ${sourceUrl}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: product.title, text, url: sourceUrl });
      } else {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch { /* user dismissed */ }
  };

  // ── Ask panel ─────────────────────────────────────────────────────────────
  const handleAsk = async () => {
    const q = askInput.trim();
    if (!q || !onAsk) return;
    setAskLoading(true);
    setAskAnswer("");
    try {
      const answer = await onAsk(q);
      setAskAnswer(answer);
    } catch {
      setAskAnswer("Sorry, couldn't get an answer right now.");
    } finally {
      setAskLoading(false);
    }
  };

  const toggleAsk = () => {
    setAskOpen(v => !v);
    if (!askOpen) setTimeout(() => askRef.current?.focus(), 150);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden w-full shadow-sm hover:shadow-md transition-shadow"
    >
      {/* Alternate pick banner */}
      {pickNumber > 1 && (
        <div className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-50 dark:bg-amber-950/60 border-b border-amber-100 dark:border-amber-900">
          <span className="text-xs text-amber-700 dark:text-amber-400 font-medium">
            #{pickNumber} pick — step down from best match
          </span>
        </div>
      )}

      {/* Top section */}
      <div className="flex gap-0">
        {/* Product image */}
        <div className="w-24 min-w-24 bg-indigo-50 dark:bg-indigo-950 flex items-center justify-center overflow-hidden">
          {product.image_url && !imgFailed ? (
            <div className="relative w-24 h-full min-h-24">
              {/* Shimmer skeleton while loading */}
              {!imgLoaded && (
                <div className="absolute inset-0 shimmer" />
              )}
              <Image
                src={product.image_url}
                alt={product.title}
                fill
                className={`object-cover transition-opacity duration-500 ${imgLoaded ? "opacity-100" : "opacity-0"}`}
                sizes="96px"
                unoptimized
                onError={() => setImgFailed(true)}
                onLoad={() => setImgLoaded(true)}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center w-full h-24">
              <TrendingUp size={28} className="text-indigo-300" />
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 p-3.5">
          {/* Badges */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300">
              {pickNumber === 1 ? "Best match" : `Pick #${pickNumber}`}
            </span>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${regret.bg} ${regret.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${regret.dot}`} />
              {regret.label}
            </span>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
              {confidence_score}% confidence
            </span>
            {product.source && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">
                {sourceLabel}
              </span>
            )}
          </div>

          {/* Name + price */}
          <p className="font-semibold text-sm text-gray-900 dark:text-white leading-tight mb-0.5">
            {product.title}
          </p>
          <div className="flex items-center gap-2 mb-1.5">
            <p className="text-sm text-gray-500">
              ₹{product.price.toLocaleString("en-IN")}
            </p>
            {product.rating && (
              <span className="flex items-center gap-0.5 text-xs text-amber-500 font-medium">
                <Star size={10} className="fill-amber-400 text-amber-400" />
                {product.rating.toFixed(1)}
                {product.review_count && (
                  <span className="text-gray-400 font-normal ml-0.5">
                    ({product.review_count.toLocaleString("en-IN")})
                  </span>
                )}
              </span>
            )}
          </div>
          {product.review_highlight && (
            <p className="text-xs text-gray-500 dark:text-gray-400 italic mb-2 leading-snug">
              💬 &ldquo;{product.review_highlight}&rdquo;
            </p>
          )}

          {/* Reasoning — skeleton while waiting for first tokens */}
          {!reasoning && isStreaming ? (
            <div className="space-y-1.5 mb-2.5">
              <div className="shimmer h-2.5 rounded-full w-full" />
              <div className="shimmer h-2.5 rounded-full w-[85%]" />
              <div className="shimmer h-2.5 rounded-full w-[65%]" />
            </div>
          ) : (
            <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed mb-2.5">
              {reasoning || "Analysing match…"}
              {isStreaming && reasoning && (
                <span className="streaming-cursor" />
              )}
            </p>
          )}

          {/* Tradeoff */}
          {tradeoff && (
            <div className="text-xs italic text-gray-500 border-l-2 border-gray-200 dark:border-gray-700 pl-2.5 py-0.5">
              Tradeoff: {tradeoff}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons row */}
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-2.5 border-t border-gray-100 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/60">
        {/* Add to Cart — Shopify only */}
        {cartUrl && (
          <motion.a
            href={cartUrl}
            target="_blank"
            rel="noopener noreferrer"
            whileTap={{ scale: 0.95 }}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-all shadow-sm"
          >
            <ShoppingCart size={12} />
            Add to Cart
          </motion.a>
        )}

        {/* View on source */}
        <motion.button
          onClick={() => window.open(sourceUrl, "_blank")}
          whileTap={{ scale: 0.95 }}
          className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 border border-gray-200 dark:border-gray-700 hover:border-indigo-300 hover:text-indigo-600 text-gray-600 dark:text-gray-400 rounded-lg transition-all bg-white dark:bg-gray-900"
        >
          <ExternalLink size={11} />
          {cartUrl ? "View" : `View on ${sourceLabel}`}
        </motion.button>

        {/* Ask anything */}
        {onAsk && (
          <motion.button
            onClick={toggleAsk}
            whileTap={{ scale: 0.95 }}
            className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all border ${
              askOpen
                ? "bg-indigo-50 dark:bg-indigo-950 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300"
                : "border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-indigo-300 hover:text-indigo-600 bg-white dark:bg-gray-900"
            }`}
          >
            <MessageCircle size={11} />
            Ask
            <ChevronDown size={10} className={`transition-transform ${askOpen ? "rotate-180" : ""}`} />
          </motion.button>
        )}

        {/* Read aloud */}
        <motion.button
          onClick={handleSpeak}
          whileTap={{ scale: 0.95 }}
          title={isSpeaking ? "Stop reading" : "Read aloud"}
          className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all border ${
            isSpeaking
              ? "bg-violet-50 dark:bg-violet-950 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300"
              : "border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-violet-300 hover:text-violet-600 bg-white dark:bg-gray-900"
          }`}
        >
          {isSpeaking ? (
            <span className="flex items-end gap-px" style={{ height: 11 }}>
              {[4, 8, 5, 8, 4].map((h, idx) => (
                <span key={idx} className="wave-bar bg-violet-500 rounded-sm" style={{ width: 2, height: h }} />
              ))}
            </span>
          ) : (
            <Volume2 size={11} />
          )}
          {isSpeaking ? "Stop" : "Read"}
        </motion.button>

        {/* Share */}
        <motion.button
          onClick={handleShare}
          whileTap={{ scale: 0.95 }}
          title="Share recommendation"
          className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-green-300 hover:text-green-600 bg-white dark:bg-gray-900"
        >
          <Share2 size={11} />
          {copied ? "Copied!" : "Share"}
        </motion.button>

        {/* Not this one */}
        {onReject && (
          <motion.button
            onClick={onReject}
            disabled={isRejecting}
            whileTap={{ scale: 0.95 }}
            className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all border border-gray-200 dark:border-gray-700 text-gray-400 hover:border-red-300 hover:text-red-500 disabled:opacity-40 disabled:cursor-not-allowed bg-white dark:bg-gray-900 ml-auto"
          >
            <X size={11} />
            {isRejecting ? "Finding next…" : "Not this one"}
          </motion.button>
        )}
      </div>

      {/* Ask panel */}
      <AnimatePresence>
        {askOpen && onAsk && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden border-t border-gray-100 dark:border-gray-800"
          >
            <div className="px-3.5 py-3 bg-gray-50/80 dark:bg-gray-900/80">
              <p className="text-xs text-gray-400 mb-2">Ask anything about this product</p>
              <div className="flex gap-2">
                <input
                  ref={askRef}
                  value={askInput}
                  onChange={e => setAskInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") handleAsk(); }}
                  placeholder="Is it good for heavy use? Does it have warranty?"
                  className="flex-1 text-xs px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
                <button
                  onClick={handleAsk}
                  disabled={!askInput.trim() || askLoading}
                  className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 transition-all active:scale-95"
                >
                  <Send size={12} />
                </button>
              </div>
              <AnimatePresence>
                {(askLoading || askAnswer) && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-lg px-3 py-2"
                  >
                    {askLoading ? (
                      <span className="flex items-center gap-1.5">
                        <span className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                      </span>
                    ) : askAnswer}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Regret footer */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-t border-gray-100 dark:border-gray-800">
        {regret_scenario ? (
          <div className="flex items-start gap-1.5 flex-1">
            <AlertCircle size={12} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-gray-500 leading-snug">
              Regret if: {regret_scenario}
            </p>
          </div>
        ) : (
          <div />
        )}
      </div>

      {/* Elimination panel */}
      <EliminationPanel eliminated={elimination} />
    </motion.div>
  );
}
