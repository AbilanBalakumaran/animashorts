"use client";

import { motion } from "framer-motion";
import { clsx } from "clsx";

export const STYLES = [
  {
    id: "oceanic",
    label: "Oceanic",
    emoji: "🌊",
    description: "Deep sea blues, bioluminescent glow",
    gradient: "from-blue-900 to-cyan-800",
  },
  {
    id: "emotional",
    label: "Emotional",
    emoji: "✨",
    description: "Golden hour, warm tones, tearful",
    gradient: "from-amber-900 to-orange-700",
  },
  {
    id: "epic",
    label: "Epic Battle",
    emoji: "⚔️",
    description: "Dramatic action, intense lighting",
    gradient: "from-red-900 to-rose-700",
  },
  {
    id: "mysterious",
    label: "Mysterious",
    emoji: "🌙",
    description: "Dark fog, moonlight, silhouettes",
    gradient: "from-purple-900 to-indigo-800",
  },
  {
    id: "documentary",
    label: "Documentary",
    emoji: "🎌",
    description: "Clean composition, neutral tones",
    gradient: "from-slate-800 to-slate-700",
  },
];

interface Props {
  value: string;
  onChange: (style: string) => void;
}

export default function StylePicker({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {STYLES.map((style) => (
        <motion.button
          key={style.id}
          type="button"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => onChange(style.id)}
          className={clsx(
            "relative rounded-xl p-3 text-left transition-all border-2",
            value === style.id
              ? "border-cyan-400 bg-gradient-to-br " + style.gradient + " shadow-lg shadow-cyan-500/20"
              : "border-white/10 bg-white/5 hover:border-white/20"
          )}
        >
          <div className="text-2xl mb-1">{style.emoji}</div>
          <div className="font-semibold text-sm text-white">{style.label}</div>
          <div className="text-xs text-white/60 mt-0.5 leading-tight">{style.description}</div>
          {value === style.id && (
            <motion.div
              layoutId="style-indicator"
              className="absolute top-2 right-2 w-2 h-2 rounded-full bg-cyan-400"
            />
          )}
        </motion.button>
      ))}
    </div>
  );
}
