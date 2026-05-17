import os
import shutil
from pathlib import Path

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))


def job_dir(job_id: str) -> Path:
    d = OUTPUT_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def narration_path(job_id: str) -> Path:
    return job_dir(job_id) / "narration.mp3"


def image_path(job_id: str, scene_id: int) -> Path:
    return job_dir(job_id) / f"scene_{scene_id:02d}.png"


def output_video_path(job_id: str) -> Path:
    return job_dir(job_id) / "final_short.mp4"


def subtitles_path(job_id: str) -> Path:
    return job_dir(job_id) / "subtitles.srt"


def cleanup_job(job_id: str) -> None:
    d = OUTPUT_DIR / job_id
    if d.exists():
        shutil.rmtree(d)


def output_url(job_id: str) -> str:
    base = os.getenv("PUBLIC_API_URL", "")
    if base:
        return f"{base.rstrip('/')}/api/stream/{job_id}"
    return f"/api/stream/{job_id}"
