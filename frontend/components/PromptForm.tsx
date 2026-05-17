"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { generateVideo } from "@/lib/api";
import StylePicker from "./StylePicker";

const DURATIONS = [
  { value: 16, label: "16s", desc: "Ultra Short" },
  { value: 30, label: "30s", desc: "Standard" },
  { value: 60, label: "60s", desc: "Long Form" },
];

const EXAMPLES = [
  "Jinbe's original design evolution in One Piece. Calm oceanic atmosphere.",
  "Luffy's transformation from chapter 1 to Gear 5. Epic cinematic.",
  "The history of the Void Century. Dark mysterious atmosphere.",
  "Zoro's greatest sword techniques throughout the series. Intense battle style.",
];

export default function PromptForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [scriptHint, setScriptHint] = useState("");
  const [style, setStyle] = useState("oceanic");
  const [duration, setDuration] = useState(16);
  const [subtitles, setSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { job_id } = await generateVideo({
        topic: topic.trim(),
        script_hint: scriptHint.trim() || undefined,
        style,
        duration_seconds: duration,
        subtitles,
      });
      router.push(`/generate?id=${job_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to start generation");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Topic input */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">
          Topic or Idea
        </label>
        <div className="relative">
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Jinbe's original design evolution in One Piece…"
            rows={3}
            maxLength={500}
            required
            className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-white placeholder-white/30
                       focus:outline-none focus:border-cyan-400/60 focus:ring-1 focus:ring-cyan-400/30
                       resize-none transition-all text-sm"
          />
          <div className="absolute bottom-2 right-3 text-xs text-white/30">
            {topic.length}/500
          </div>
        </div>
        {/* Example prompts */}
        <div className="flex flex-wrap gap-2 mt-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setTopic(ex)}
              className="text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-white/50
                         hover:text-white/80 border border-white/10 transition-all"
            >
              {ex.slice(0, 32)}…
            </button>
          ))}
        </div>
      </div>

      {/* Duration selector */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">Duration</label>
        <div className="flex gap-3">
          {DURATIONS.map((d) => (
            <button
              key={d.value}
              type="button"
              onClick={() => setDuration(d.value)}
              className={`flex-1 py-2.5 rounded-xl border text-sm font-semibold transition-all
                ${duration === d.value
                  ? "bg-cyan-500/20 border-cyan-400 text-cyan-300"
                  : "bg-white/5 border-white/10 text-white/60 hover:border-white/20"
                }`}
            >
              {d.label}
              <div className="text-xs font-normal text-white/40">{d.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Style picker */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">Visual Style</label>
        <StylePicker value={style} onChange={setStyle} />
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-sm text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
      >
        <span>{showAdvanced ? "▲" : "▼"}</span>
        Advanced options
      </button>

      <AnimatePresence>
        {showAdvanced && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-4 overflow-hidden"
          >
            <div className="space-y-2">
              <label className="block text-sm font-medium text-white/80">
                Narration Hint <span className="text-white/40 font-normal">(optional)</span>
              </label>
              <textarea
                value={scriptHint}
                onChange={(e) => setScriptHint(e.target.value)}
                placeholder="Optional: provide a rough script idea or key points to cover…"
                rows={3}
                maxLength={1000}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-white
                           placeholder-white/30 focus:outline-none focus:border-cyan-400/60
                           focus:ring-1 focus:ring-cyan-400/30 resize-none transition-all text-sm"
              />
            </div>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={subtitles}
                  onChange={(e) => setSubtitles(e.target.checked)}
                  className="sr-only"
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${subtitles ? "bg-cyan-500" : "bg-white/20"}`} />
                <div className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform
                  ${subtitles ? "translate-x-4" : "translate-x-0"}`} />
              </div>
              <span className="text-sm text-white/70 group-hover:text-white/90 transition-colors">
                Burn subtitles into video
              </span>
            </label>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <motion.button
        type="submit"
        disabled={loading || !topic.trim()}
        whileHover={{ scale: loading ? 1 : 1.02 }}
        whileTap={{ scale: loading ? 1 : 0.98 }}
        className="w-full py-4 rounded-2xl font-bold text-base tracking-wide transition-all
                   bg-gradient-to-r from-cyan-500 to-blue-600 text-white
                   disabled:opacity-50 disabled:cursor-not-allowed
                   hover:from-cyan-400 hover:to-blue-500
                   shadow-lg shadow-cyan-500/20"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Starting generation…
          </span>
        ) : (
          "✨ Generate Anime Short"
        )}
      </motion.button>
    </form>
  );
}
