"use client";

import { motion } from "framer-motion";
import PromptForm from "@/components/PromptForm";
import Link from "next/link";

const PARTICLES = Array.from({ length: 20 }, (_, i) => ({
  id: i,
  x: Math.random() * 100,
  y: Math.random() * 100,
  size: Math.random() * 3 + 1,
  delay: Math.random() * 5,
}));

export default function HomePage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-b from-ocean-dark via-ocean-mid/40 to-ocean-dark pointer-events-none" />

      {/* Animated particles */}
      <div className="fixed inset-0 pointer-events-none">
        {PARTICLES.map((p) => (
          <motion.div
            key={p.id}
            className="absolute rounded-full bg-cyan-400/20"
            style={{ left: `${p.x}%`, top: `${p.y}%`, width: p.size, height: p.size }}
            animate={{ y: [0, -30, 0], opacity: [0.2, 0.6, 0.2] }}
            transition={{ duration: 4 + p.delay, repeat: Infinity, delay: p.delay }}
          />
        ))}
      </div>

      {/* Radial glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2
                        w-[600px] h-[600px] rounded-full
                        bg-cyan-500/5 blur-3xl" />
      </div>

      <div className="relative z-10 max-w-2xl mx-auto px-4 py-16">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full
                          bg-cyan-500/10 border border-cyan-500/20 text-cyan-400
                          text-xs font-medium mb-6">
            <span className="animate-pulse w-1.5 h-1.5 rounded-full bg-cyan-400" />
            AI-Powered Anime Shorts Generator
          </div>

          <h1 className="text-5xl font-extrabold tracking-tight mb-4">
            <span className="text-white">Anima</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              Shorts
            </span>
          </h1>

          <p className="text-lg text-white/50 max-w-md mx-auto leading-relaxed">
            Turn any anime topic into a fully edited{" "}
            <span className="text-white/80">TikTok-ready vertical short</span> with AI narration,
            cinematic visuals, and dynamic music.
          </p>

          {/* Stats row */}
          <div className="flex justify-center gap-8 mt-8">
            {[
              { value: "9:16", label: "Format" },
              { value: "1080p", label: "Resolution" },
              { value: "< 2min", label: "Generation" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-xl font-bold text-cyan-400">{stat.value}</div>
                <div className="text-xs text-white/40 mt-0.5">{stat.label}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Form card */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="rounded-3xl bg-white/[0.04] border border-white/10 p-6 sm:p-8
                     backdrop-blur-sm glow-border"
        >
          <PromptForm />
        </motion.div>

        {/* Gallery link */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center mt-6"
        >
          <Link
            href="/gallery"
            className="text-sm text-white/40 hover:text-white/70 transition-colors"
          >
            View past generations →
          </Link>
        </motion.div>

        {/* Feature pills */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="flex flex-wrap justify-center gap-2 mt-10"
        >
          {[
            "🎙️ AI Voice-over",
            "🎨 Anime Visuals",
            "🎬 Ken Burns Effects",
            "🎵 Auto Music",
            "⚡ Transitions",
            "📱 TikTok Ready",
          ].map((feat) => (
            <span
              key={feat}
              className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-white/50"
            >
              {feat}
            </span>
          ))}
        </motion.div>
      </div>
    </div>
  );
}
