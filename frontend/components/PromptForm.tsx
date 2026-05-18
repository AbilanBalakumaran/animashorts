"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { generateVideo } from "@/lib/api";

const DURATIONS = [
  { value: 16, label: "16s", desc: "Ultra Short" },
  { value: 30, label: "30s", desc: "Standard" },
  { value: 60, label: "60s", desc: "Long Form" },
];

export default function PromptForm() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [topic, setTopic] = useState("");
  const [scriptHint, setScriptHint] = useState("");
  const [duration, setDuration] = useState(16);
  const [subtitles, setSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  // "upload" = user provides images | "ai" = AI generates images automatically
  const [imageMode, setImageMode] = useState<"upload" | "ai">("ai");

  function handleFiles(files: FileList | null) {
    if (!files) return;
    const valid = Array.from(files).filter((f) =>
      ["image/jpeg", "image/png", "image/webp"].includes(f.type)
    );
    const merged = [...images, ...valid].slice(0, 20);
    setImages(merged);
    const urls = merged.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
  }

  function removeImage(i: number) {
    const next = images.filter((_, idx) => idx !== i);
    setImages(next);
    setPreviews(next.map((f) => URL.createObjectURL(f)));
  }

  function switchMode(mode: "upload" | "ai") {
    setImageMode(mode);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    if (imageMode === "upload" && images.length === 0) {
      setError("Please add at least one image, or switch to AI image generation.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { job_id } = await generateVideo({
        topic: topic.trim(),
        script_hint: scriptHint.trim() || undefined,
        style: "documentary",
        duration_seconds: duration,
        subtitles,
        images: imageMode === "upload" ? images : [],
      });
      router.push(`/generate?id=${job_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to start generation");
      setLoading(false);
    }
  }

  const canSubmit = !loading && topic.trim().length > 0 &&
    (imageMode === "ai" || images.length > 0);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">

      {/* ── Image mode toggle ─────────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-white/80">Images</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => switchMode("ai")}
            className={`relative rounded-xl border px-4 py-3 text-sm font-semibold transition-all text-left
              ${imageMode === "ai"
                ? "bg-cyan-500/20 border-cyan-400 text-cyan-300"
                : "bg-white/5 border-white/10 text-white/50 hover:border-white/20"
              }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">✨</span>
              <span>AI génère les images</span>
            </div>
            <div className="text-xs font-normal text-white/40 leading-snug">
              L&apos;IA crée les visuels automatiquement — sait à quoi ressemblent Oda, Jinbei, etc.
            </div>
            {imageMode === "ai" && (
              <span className="absolute top-2 right-2 text-xs bg-cyan-500 text-white px-1.5 py-0.5 rounded-full">
                Actif
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => switchMode("upload")}
            className={`relative rounded-xl border px-4 py-3 text-sm font-semibold transition-all text-left
              ${imageMode === "upload"
                ? "bg-cyan-500/20 border-cyan-400 text-cyan-300"
                : "bg-white/5 border-white/10 text-white/50 hover:border-white/20"
              }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">🖼️</span>
              <span>Mes propres images</span>
            </div>
            <div className="text-xs font-normal text-white/40 leading-snug">
              Upload tes images — le script sera généré pour correspondre à chacune.
            </div>
            {imageMode === "upload" && (
              <span className="absolute top-2 right-2 text-xs bg-cyan-500 text-white px-1.5 py-0.5 rounded-full">
                Actif
              </span>
            )}
          </button>
        </div>

        {/* AI mode info banner */}
        <AnimatePresence>
          {imageMode === "ai" && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="rounded-xl bg-cyan-500/10 border border-cyan-400/20 px-4 py-3 text-sm text-cyan-200/70">
                <div className="flex items-start gap-2">
                  <span className="text-base shrink-0">🤖</span>
                  <div>
                    <p className="font-medium text-cyan-300 mb-0.5">Génération automatique activée</p>
                    <p className="text-xs text-white/50">
                      L&apos;IA écrit le script et génère les images correspondantes.
                      Si tu mentionnes un personnage (ex: Jinbei, Oda), il saura à quoi il ressemble.
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Upload mode: drop zone + thumbnails */}
        <AnimatePresence>
          {imageMode === "upload" && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden space-y-3"
            >
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
                className="relative cursor-pointer rounded-2xl border-2 border-dashed border-white/20
                           hover:border-cyan-400/50 bg-white/[0.03] hover:bg-white/[0.06]
                           transition-all flex flex-col items-center justify-center gap-2 py-8 px-4"
              >
                <div className="text-3xl">🖼️</div>
                <p className="text-sm text-white/50">Click or drag & drop your images here</p>
                <p className="text-xs text-white/30">JPG, PNG, WEBP — max 20 images</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  multiple
                  className="hidden"
                  onChange={(e) => handleFiles(e.target.files)}
                />
              </div>

              {previews.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {previews.map((src, i) => (
                    <div key={i} className="relative group w-16 h-16 rounded-xl overflow-hidden border border-white/10">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt="" className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() => removeImage(i)}
                        className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100
                                   transition-opacity flex items-center justify-center text-white text-lg"
                      >
                        ×
                      </button>
                      <span className="absolute bottom-0 left-0 right-0 text-center text-[9px] text-white/70 bg-black/50 py-px">
                        {i + 1}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Topic / script prompt ─────────────────────────────────────── */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">
          Ton prompt ou script complet
        </label>
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder={imageMode === "ai"
            ? `Décris la vidéo que tu veux — l'IA s'occupe des images.\n\nExemple: "Fais un short sur l'évolution de Jinbei dans One Piece. Commence par ses origines de chasseur de primes, montre son amitié avec Luffy, termine avec son rôle de timonier. Ton épique et océanique."`
            : `Décris ta vidéo en détail, ou colle ton script complet.\n\nExemple: "Short cinématique sur l'évolution du design de Jinbei dans One Piece. Ton émotionnel et océanique."`
          }
          rows={7}
          maxLength={8000}
          required
          className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-white
                     placeholder-white/30 focus:outline-none focus:border-cyan-400/60
                     focus:ring-1 focus:ring-cyan-400/30 resize-y transition-all text-sm"
        />
        <div className="text-right text-xs text-white/30">{topic.length}/8000</div>
      </div>

      {/* ── Duration ─────────────────────────────────────────────────── */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">Durée</label>
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

      {/* ── Advanced ─────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-sm text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
      >
        <span>{showAdvanced ? "▲" : "▼"}</span> Options avancées
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
                Narration Hint <span className="text-white/40 font-normal">(optionnel)</span>
              </label>
              <textarea
                value={scriptHint}
                onChange={(e) => setScriptHint(e.target.value)}
                placeholder="Optionnel: décris le ton, le style de narration ou des points clés…"
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
                <div className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${subtitles ? "translate-x-4" : ""}`} />
              </div>
              <span className="text-sm text-white/70 group-hover:text-white/90 transition-colors">
                Incruster les sous-titres dans la vidéo
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
        disabled={!canSubmit}
        whileHover={{ scale: canSubmit ? 1.02 : 1 }}
        whileTap={{ scale: canSubmit ? 0.98 : 1 }}
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
            Démarrage…
          </span>
        ) : imageMode === "ai" ? (
          "✨ Générer la vidéo avec l'IA"
        ) : (
          `✨ Générer la vidéo${images.length > 0 ? ` (${images.length} image${images.length > 1 ? "s" : ""})` : ""}`
        )}
      </motion.button>
    </form>
  );
}
