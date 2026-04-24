"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import type { ConfidenceBreakdown } from "@/lib/api";

interface JourneyStep {
  label: string;
  score: number;
}

interface Props {
  score: number;
  breakdown: ConfidenceBreakdown | null;
  journey: JourneyStep[];
}

const RADIUS = 40;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function ScoreRing({ score }: { score: number }) {
  const [displayScore, setDisplayScore] = useState(0);
  const prevScore = useRef(0);

  useEffect(() => {
    const controls = animate(prevScore.current, score, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (v) => setDisplayScore(Math.round(v)),
    });
    prevScore.current = score;
    return controls.stop;
  }, [score]);

  const offset = CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE;

  const ringColor =
    score >= 80 ? "#16a34a" : score >= 60 ? "#d97706" : "#5B4CE8";

  return (
    <div className="flex justify-center">
      <svg width="110" height="110" viewBox="0 0 100 100">
        {/* Track */}
        <circle
          cx="50" cy="50" r={RADIUS}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="8"
        />
        {/* Progress */}
        <motion.circle
          cx="50" cy="50" r={RADIUS}
          fill="none"
          stroke={ringColor}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform="rotate(-90 50 50)"
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
        />
        {/* Score number */}
        <text x="50" y="46" textAnchor="middle" fontSize="20" fontWeight="600" fill="currentColor" className="fill-gray-900 dark:fill-white">
          {displayScore}%
        </text>
        <text x="50" y="60" textAnchor="middle" fontSize="9" fill="currentColor" className="fill-gray-400">
          confident
        </text>
      </svg>
    </div>
  );
}

function BreakdownRow({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const isNegative = value < 0;

  return (
    <div className="py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div className="flex justify-between items-center mb-0.5">
        <span className="text-xs text-gray-500">{label}</span>
        <span
          className={`text-xs font-medium ${
            isNegative ? "text-amber-600" : "text-gray-700 dark:text-gray-300"
          }`}
        >
          {isNegative ? value : `${value}/${max}`}
        </span>
      </div>
      <div className="h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${isNegative ? "bg-amber-400" : "bg-indigo-500"}`}
          initial={{ width: 0 }}
          animate={{ width: `${isNegative ? 100 : pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function ConfidenceMeter({ score, breakdown, journey }: Props) {
  return (
    <div className="flex flex-col gap-4">
      {/* Ring */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Purchase Confidence
        </p>
        <ScoreRing score={score} />
      </div>

      {/* Breakdown */}
      {breakdown && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Score Breakdown
          </p>
          <BreakdownRow label="Category" value={breakdown.category} max={25} />
          <BreakdownRow label="Budget" value={breakdown.budget} max={20} />
          <BreakdownRow label="Use case" value={breakdown.use_case} max={25} />
          <BreakdownRow label="Priorities" value={breakdown.priorities} max={15} />
          <BreakdownRow
            label="Ambiguity"
            value={breakdown.ambiguity_penalty}
            max={0}
          />
        </div>
      )}

      {/* Journey */}
      {journey.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Confidence Journey
          </p>
          <div className="flex flex-col gap-2">
            {journey.map((step, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    i === journey.length - 1
                      ? "bg-indigo-500 ring-2 ring-indigo-200"
                      : "bg-indigo-300"
                  }`}
                />
                <span className="text-xs text-gray-500 flex-1 truncate">
                  {step.label}
                </span>
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  {step.score}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
