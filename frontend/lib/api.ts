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

const BASE =
  typeof window !== "undefined"
    ? `${window.location.origin}/api`
    : "http://localhost:8000/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface GeneratePayload {
  topic: string;
  script_hint?: string;
  style: string;
  duration_seconds: number;
  subtitles: boolean;
  images: File[];   // empty array = AI generates images automatically
}

export async function generateVideo(payload: GeneratePayload): Promise<{ job_id: string }> {
  const fd = new FormData();
  fd.append("topic", payload.topic);
  if (payload.script_hint) fd.append("script_hint", payload.script_hint);
  fd.append("style", payload.style);
  fd.append("duration_seconds", String(payload.duration_seconds));
  fd.append("subtitles", String(payload.subtitles));
  for (const img of payload.images) {
    fd.append("images", img);
  }
  // No Content-Type header — browser sets multipart/form-data boundary automatically
  return apiFetch("/generate", { method: "POST", body: fd });
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch(`/jobs/${jobId}`);
}

export async function getVideos(): Promise<{ videos: VideoItem[] }> {
  return apiFetch("/videos");
}
