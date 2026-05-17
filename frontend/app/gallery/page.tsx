"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { getVideos, type VideoItem } from "@/lib/api";

function formatDate(ts: number) {
  return new Date(ts * 1000).toLocaleDateString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function GalleryPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getVideos()
      .then((d) => setVideos(d.videos))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="fixed inset-0 bg-gradient-to-b from-ocean-dark via-ocean-mid/30 to-ocean-dark pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-16">
        <div className="flex items-center justify-between mb-10">
          <Link href="/" className="text-sm text-white/40 hover:text-white/70 transition-colors">
            ← Generate New
          </Link>
          <h1 className="text-xl font-bold text-white">Gallery</h1>
          <div className="w-24" />
        </div>

        {loading && (
          <div className="flex justify-center py-20">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent"
            />
          </div>
        )}

        {!loading && videos.length === 0 && (
          <div className="text-center py-20 text-white/30">
            <div className="text-4xl mb-4">🎬</div>
            <p className="text-lg font-medium text-white/50">No videos yet</p>
            <p className="text-sm mt-2">Generate your first anime short to see it here</p>
            <Link
              href="/"
              className="inline-block mt-6 px-6 py-3 rounded-xl bg-cyan-500/20 border border-cyan-500/30
                         text-cyan-400 text-sm font-medium hover:bg-cyan-500/30 transition-all"
            >
              Create your first short →
            </Link>
          </div>
        )}

        {!loading && videos.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {videos.map((video, i) => (
              <motion.div
                key={video.job_id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="rounded-2xl overflow-hidden bg-white/[0.04] border border-white/10
                           hover:border-cyan-400/30 transition-all group cursor-pointer"
              >
                <div className="relative" style={{ paddingBottom: "177.78%" }}>
                  <video
                    src={video.url}
                    muted
                    loop
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover"
                    onMouseEnter={(e) => (e.currentTarget as HTMLVideoElement).play()}
                    onMouseLeave={(e) => (e.currentTarget as HTMLVideoElement).pause()}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                  <div className="absolute bottom-2 left-2 right-2">
                    <div className="text-xs text-white/70">{formatDate(video.created_at)}</div>
                    <div className="text-xs text-white/40">{video.size_mb} MB</div>
                  </div>
                </div>
                <div className="p-2 flex gap-2">
                  <a
                    href={`/api/download/${video.job_id}`}
                    download
                    className="flex-1 text-center text-xs py-1.5 rounded-lg bg-cyan-500/20
                               text-cyan-300 hover:bg-cyan-500/30 transition-all"
                    onClick={(e) => e.stopPropagation()}
                  >
                    ⬇ Download
                  </a>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
