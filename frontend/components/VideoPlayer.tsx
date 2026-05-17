"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface Props {
  jobId: string;
  outputUrl: string;
}

export default function VideoPlayer({ jobId, outputUrl }: Props) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const downloadUrl = `/api/download/${jobId}`;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-5"
    >
      {/* Video container — 9:16 aspect ratio */}
      <div className="relative mx-auto rounded-2xl overflow-hidden bg-black border border-white/10 shadow-2xl shadow-cyan-500/10"
           style={{ maxWidth: 360 }}>
        <div style={{ paddingBottom: "177.78%" }} />
        <video
          src={outputUrl}
          controls
          autoPlay
          loop
          playsInline
          className="absolute inset-0 w-full h-full object-contain"
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <motion.a
          href={downloadUrl}
          download
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="flex-1 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600
                     text-white font-semibold text-sm text-center
                     hover:from-cyan-400 hover:to-blue-500 transition-all shadow-lg shadow-cyan-500/20"
        >
          ⬇ Download MP4
        </motion.a>

        <motion.button
          onClick={copyLink}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="px-4 py-3 rounded-xl bg-white/5 border border-white/10
                     text-white/70 hover:text-white hover:border-white/20
                     text-sm font-medium transition-all"
        >
          {copied ? "✓ Copied!" : "🔗 Share"}
        </motion.button>
      </div>

      {/* Platform hints */}
      <div className="flex gap-2 justify-center">
        {["TikTok", "YouTube Shorts", "Instagram Reels"].map((platform) => (
          <span
            key={platform}
            className="text-xs px-2 py-1 rounded-full bg-white/5 border border-white/10 text-white/40"
          >
            {platform}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
