"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { EliminatedProduct } from "@/lib/api";

interface Props {
  eliminated: EliminatedProduct[];
}

export default function EliminationPanel({ eliminated }: Props) {
  const [open, setOpen] = useState(false);
  const visible = open ? eliminated : eliminated.slice(0, 3);

  if (eliminated.length === 0) return null;

  return (
    <div className="border-t border-gray-100 dark:border-gray-800">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
      >
        <span className="font-medium">
          Why {eliminated.length} other{eliminated.length !== 1 ? "s were" : " was"} ruled out
        </span>
        {open ? (
          <ChevronUp size={14} />
        ) : (
          <ChevronDown size={14} />
        )}
      </button>

      <AnimatePresence>
        {(open || eliminated.length <= 3) && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3 flex flex-col gap-1">
              {visible.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between py-1.5 border-b border-gray-50 dark:border-gray-800 last:border-0"
                >
                  <span className="text-xs text-gray-600 dark:text-gray-400 truncate max-w-[55%]">
                    {item.title}
                  </span>
                  <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 px-2 py-0.5 rounded-full ml-2 shrink-0">
                    {item.reason}
                  </span>
                </div>
              ))}
              {!open && eliminated.length > 3 && (
                <button
                  onClick={() => setOpen(true)}
                  className="text-xs text-indigo-500 hover:text-indigo-600 text-left pt-1"
                >
                  + {eliminated.length - 3} more
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
