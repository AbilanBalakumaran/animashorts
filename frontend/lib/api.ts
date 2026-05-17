export interface GeneratePayload {
  topic: string;
  script_hint?: string;
  style: string;
  duration_seconds: number;
  subtitles: boolean;
}

export interface JobStatus {
  job_id: string;
  step: "queued" | "script" | "tts" | "images" | "render" | "done" | "error";
  progress: number;
  label: string;
  output_url: string | null;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export interface VideoItem {
  job_id: string;
  url: string;
  created_at: number;
  size_mb: number;
}

const BASE = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function generateVideo(payload: GeneratePayload): Promise<{ job_id: string }> {
  return apiFetch("/generate", { method: "POST", body: JSON.stringify(payload) });
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch(`/jobs/${jobId}`);
}

export async function getVideos(): Promise<{ videos: VideoItem[] }> {
  return apiFetch("/videos");
}
