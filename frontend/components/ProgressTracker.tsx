"use client";

import { motion } from "framer-motion";
import { clsx } from "clsx";
import type { JobStatus } from "@/lib/api";

const STEPS = [
  { key: "script",  label: "Writing Script",    icon: "📝" },
  { key: "tts",     label: "Voice Generation",  icon: "🎙️" },
  { key: "images",  label: "Anime Visuals",      icon: "🎨" },
  { key: "render",  label: "Rendering Video",   icon: "🎬" },
  { key: "done",    label: "Complete",           icon: "✅" },
];

function stepIndex(step: string) {
  const idx = STEPS.findIndex((s) => s.key === step);
  return idx === -1 ? 0 : idx;
}

export default function ProgressTracker({ status }: { status: JobStatus }) {
  const current = stepIndex(status.step);
  const isError = status.step === "error";

  return (
    <div className="space-y-6">
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-white/60">
          <span>{status.label}</span>
          <span>{status.progress}%</span>
        </div>
        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
          <motion.div
            className={clsx(
              "h-full rounded-full",
              isError ? "bg-red-500" : "bg-gradient-to-r from-cyan-400 to-blue-500"
            )}
            initial={{ width: 0 }}
            animate={{ width: `${status.progress}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Step list */}
      <div className="space-y-3">
        {STEPS.map((step, idx) => {
          const isDone = idx < current || status.step === "done";
          const isActive = !isError && idx === current && status.step !== "done";

          return (
            <div key={step.key} className="flex items-center gap-3">
              {/* Icon */}
              <div
                className={clsx(
                  "w-9 h-9 rounded-full flex items-center justify-center text-lg transition-all flex-shrink-0",
                  isDone  && "bg-cyan-500/20 border border-cyan-400/50",
                  isActive && "bg-cyan-500/30 border border-cyan-400 shadow-lg shadow-cyan-500/30",
                  !isDone && !isActive && "bg-white/5 border border-white/10"
                )}
              >
                {isActive ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                    className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent"
                  />
                ) : (
                  <span className={!isDone ? "opacity-30" : ""}>{step.icon}</span>
                )}
              </div>

              {/* Label */}
              <span
                className={clsx(
                  "text-sm font-medium transition-colors",
                  isDone   && "text-cyan-300",
                  isActive && "text-white",
                  !isDone && !isActive && "text-white/30"
                )}
              >
                {step.label}
              </span>

              {/* Done check */}
              {isDone && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="ml-auto text-cyan-400 text-xs"
                >
                  ✓
                </motion.span>
              )}
            </div>
          );
        })}
      </div>

      {isError && status.error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">
          <span className="font-semibold">Error: </span>{status.error}
        </div>
      )}
    </div>
  );
}
