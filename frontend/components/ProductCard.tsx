"use client";

import { motion } from "framer-motion";
import { ShoppingCart, AlertCircle, TrendingUp } from "lucide-react";
import Image from "next/image";
import EliminationPanel from "./EliminationPanel";
import type { RecommendationData } from "@/lib/api";

interface Props {
  data: RecommendationData;
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

export default function ProductCard({ data }: Props) {
  const { product, reasoning, regret_risk, regret_scenario, tradeoff, confidence_score, elimination } = data;
  const regret = REGRET_CONFIG[regret_risk] || REGRET_CONFIG.low;

  const handleAddToCart = async () => {
    if (!product.variant_id) return;
    // Cart URL is generated server-side; for demo we open a Shopify cart URL
    // In full implementation: call /api/cart endpoint to get checkout URL
    window.open(`https://checkout.shopify.com`, "_blank");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden w-full"
    >
      {/* Top section */}
      <div className="flex gap-0">
        {/* Product image */}
        <div className="w-24 min-w-24 bg-indigo-50 dark:bg-indigo-950 flex items-center justify-center">
          {product.image_url ? (
            <div className="relative w-24 h-full min-h-24">
              <Image
                src={product.image_url}
                alt={product.title}
                fill
                className="object-cover"
                sizes="96px"
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
              Best match
            </span>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${regret.bg} ${regret.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${regret.dot}`} />
              {regret.label}
            </span>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
              {confidence_score}% confidence
            </span>
          </div>

          {/* Name + price */}
          <p className="font-semibold text-sm text-gray-900 dark:text-white leading-tight mb-0.5">
            {product.title}
          </p>
          <p className="text-sm text-gray-500 mb-2.5">
            ₹{product.price.toLocaleString("en-IN")}
          </p>

          {/* Reasoning */}
          <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed mb-2.5">
            {reasoning}
          </p>

          {/* Tradeoff */}
          {tradeoff && (
            <div className="text-xs italic text-gray-500 border-l-2 border-gray-200 dark:border-gray-700 pl-2.5 py-0.5">
              Tradeoff: {tradeoff}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-t border-gray-100 dark:border-gray-800">
        {regret_scenario ? (
          <div className="flex items-start gap-1.5 flex-1 mr-3">
            <AlertCircle size={12} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-gray-500 leading-snug">
              Regret if: {regret_scenario}
            </p>
          </div>
        ) : (
          <div />
        )}
        <button
          onClick={handleAddToCart}
          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white rounded-lg transition-all flex-shrink-0"
        >
          <ShoppingCart size={12} />
          Add to cart
        </button>
      </div>

      {/* Elimination panel */}
      <EliminationPanel eliminated={elimination} />
    </motion.div>
  );
}
