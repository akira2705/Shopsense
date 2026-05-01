"use client";

import { motion } from "framer-motion";
import { Sparkles, ExternalLink, TrendingDown } from "lucide-react";
import type { BudgetPickData } from "@/lib/api";

interface Props {
  data: BudgetPickData;
}

export default function BudgetOptimizerCard({ data }: Props) {
  const { product, savings, fit_pct } = data;

  const sourceUrl = product.url || `https://shopsense-rueprzpz.myshopify.com/products/${product.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.2 }}
      className="rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/60 dark:bg-emerald-950/40 overflow-hidden w-full"
    >
      {/* Header badge */}
      <div className="flex items-center gap-2 px-3.5 pt-2.5 pb-1.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
          <TrendingDown size={12} />
          Budget Pick — Save ₹{savings.toLocaleString("en-IN")}
        </div>
        <span className="ml-auto text-xs text-emerald-600 dark:text-emerald-500 font-medium">
          {fit_pct}% as good
        </span>
      </div>

      {/* Product row */}
      <div className="flex items-center gap-3 px-3.5 pb-2.5">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 leading-tight truncate">
            {product.title}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-emerald-700 dark:text-emerald-400 font-semibold">
              ₹{product.price.toLocaleString("en-IN")}
            </p>
            {product.rating && (
              <span className="text-xs text-gray-400">
                ★ {product.rating.toFixed(1)}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-snug">
            <Sparkles size={10} className="inline mr-1 text-emerald-500" />
            {fit_pct}% of the performance at a lower price point
          </p>
        </div>

        <button
          onClick={() => window.open(sourceUrl, "_blank")}
          className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white rounded-lg transition-all flex-shrink-0"
        >
          <ExternalLink size={11} />
          View
        </button>
      </div>
    </motion.div>
  );
}
