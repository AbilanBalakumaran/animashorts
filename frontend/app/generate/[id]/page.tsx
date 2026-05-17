"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { getJobStatus, type JobStatus } from "@/lib/api";
import ProgressTracker from "@/components/ProgressTracker";
import VideoPlayer from "@/components/VideoPlayer";

export default function GeneratePage({ params }: { params: { id: string } }) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const data = await getJobStatus(params.id);
        setStatus(data);
        if (data.step === "done" || data.step === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (err: any) {
        setError(err.message || "Failed to fetch job status");
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [params.id]);

  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="fixed inset-0 bg-gradient-to-b from-ocean-dark via-ocean-mid/40 to-ocean-dark pointer-events-none" />
      <div className="fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2
                      w-[500px] h-[500px] rounded-full bg-cyan-500/5 blur-3xl pointer-events-none" />

      <div className="relative z-10 max-w-lg mx-auto px-4 py-16">
        {/* Nav */}
        <div className="flex items-center justify-between mb-10">
          <Link href="/" className="text-sm text-white/40 hover:text-white/70 transition-colors">
            ← New Video
          </Link>
          <Link href="/gallery" className="text-sm text-white/40 hover:text-white/70 transition-colors">
            Gallery →
          </Link>
        </div>

        {/* Job ID badge */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-xs text-white/30 font-mono
                          bg-white/5 border border-white/10 px-3 py-1 rounded-full">
            Job: {params.id.slice(0, 8)}…
          </div>
        </div>

        {error && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300 mb-6">
            {error}
          </div>
        )}

        {!status && !error && (
          <div className="flex flex-col items-center gap-4 py-16 text-white/40">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent"
            />
            <span className="text-sm">Connecting…</span>
          </div>
        )}

        {status && status.step !== "done" && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-3xl bg-white/[0.04] border border-white/10 p-6 sm:p-8 backdrop-blur-sm"
          >
            <h2 className="text-xl font-bold text-white mb-6 text-center">
              {status.step === "error" ? "Generation Failed" : "Generating your short…"}
            </h2>
            <ProgressTracker status={status} />
          </motion.div>
        )}

        {status && status.step === "done" && status.output_url && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-1">Your short is ready!</h2>
              <p className="text-white/40 text-sm">Tap play, download, or share directly to TikTok</p>
            </div>
            <VideoPlayer jobId={params.id} outputUrl={status.output_url} />
          </motion.div>
        )}
      </div>
    </div>
  );
}
