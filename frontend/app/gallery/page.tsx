"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { getVideos, type VideoItem } from "@/lib/api";

function timeAgo(ts: number) {
  const diff = (Date.now() / 1000) - ts;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function GalleryPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState<string | null>(null);

  useEffect(() => {
    getVideos().then((d) => setVideos(d.videos)).finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="fixed inset-0 bg-gradient-to-b from-ocean-dark via-ocean-mid/30 to-ocean-dark pointer-events-none" />
      <div className="relative z-10 max-w-4xl mx-auto px-4 py-16">

        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <Link href="/" className="text-sm text-white/40 hover:text-white/70 transition-colors">← Generate New</Link>
          <h1 className="text-xl font-bold text-white">My Videos</h1>
          <div className="text-sm text-white/30">{videos.length} video{videos.length !== 1 ? "s" : ""}</div>
        </div>

        {loading && (
          <div className="flex justify-center py-20">
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent" />
          </div>
        )}

        {!loading && videos.length === 0 && (
          <div className="text-center py-20 text-white/30">
            <div className="text-5xl mb-4">🎬</div>
            <p className="text-lg font-medium text-white/50">No videos yet</p>
            <p className="text-sm mt-2">Generate your first short to see it here</p>
            <Link href="/" className="inline-block mt-6 px-6 py-3 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-sm font-medium hover:bg-cyan-500/30 transition-all">
              Create your first short →
            </Link>
          </div>
        )}

        {!loading && videos.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {videos.map((video, i) => (
              <motion.div key={video.job_id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                className="rounded-2xl overflow-hidden bg-white/[0.04] border border-white/10 hover:border-cyan-400/40 transition-all group">

                {/* Video thumbnail */}
                <div className="relative" style={{ paddingBottom: "177.78%" }}>
                  <video
                    src={video.url}
                    muted
                    loop
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover"
                    onMouseEnter={(e) => { (e.currentTarget as HTMLVideoElement).play(); setPlaying(video.job_id); }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLVideoElement).pause(); setPlaying(null); }}
                    onClick={(e) => {
                      const v = e.currentTarget as HTMLVideoElement;
                      v.paused ? v.play() : v.pause();
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent pointer-events-none" />

                  {/* Play icon overlay */}
                  {playing !== video.job_id && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                      <div className="w-10 h-10 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-white text-lg ml-0.5">▶</span>
                      </div>
                    </div>
                  )}

                  {/* Meta */}
                  <div className="absolute bottom-2 left-2 right-2 pointer-events-none">
                    <div className="text-[10px] text-white/60">{timeAgo(video.created_at)}</div>
                    <div className="text-[10px] text-white/40">{video.size_mb} MB</div>
                  </div>
                </div>

                {/* Actions */}
                <div className="p-2 flex gap-1.5">
                  <a href={`/api/download/${video.job_id}`} download
                    className="flex-1 text-center text-xs py-2 rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-all font-medium">
                    ⬇ Download
                  </a>
                  <Link href={`/generate/?id=${video.job_id}`}
                    className="px-2 text-xs py-2 rounded-lg bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 transition-all">
                    👁
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
