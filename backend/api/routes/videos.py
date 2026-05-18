import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs")).resolve()

router = APIRouter()


def _video_path(job_id: str) -> Path:
    return OUTPUT_DIR / job_id / "final_short.mp4"


@router.get("/videos")
async def list_videos():
    videos = []
    if OUTPUT_DIR.exists():
        for job_dir in sorted(OUTPUT_DIR.iterdir(), reverse=True):
            video_file = job_dir / "final_short.mp4"
            if video_file.exists():
                videos.append({
                    "job_id": job_dir.name,
                    "url": f"/api/stream/{job_dir.name}",
                    "created_at": video_file.stat().st_mtime,
                    "size_mb": round(video_file.stat().st_size / 1_048_576, 2),
                })
    return {"videos": videos}


@router.get("/stream/{job_id}")
async def stream_video(job_id: str):
    """Serve video for browser <video> element.
    FileResponse handles Range requests (206) natively — no custom parsing needed."""
    video_file = _video_path(job_id)
    if not video_file.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_file}")
    return FileResponse(
        path=str(video_file),
        media_type="video/mp4",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/download/{job_id}")
async def download_video(job_id: str):
    video_file = _video_path(job_id)
    if not video_file.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_file}")
    return FileResponse(
        path=str(video_file),
        media_type="video/mp4",
        filename=f"animashort_{job_id[:8]}.mp4",
    )


@router.get("/debug/{job_id}")
async def debug_job(job_id: str):
    """Diagnostic endpoint — shows what files exist for a job."""
    job_dir = OUTPUT_DIR / job_id
    video_file = job_dir / "final_short.mp4"
    files = []
    if job_dir.exists():
        files = [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in sorted(job_dir.iterdir())
        ]
    return {
        "job_id": job_id,
        "output_dir": str(OUTPUT_DIR),
        "job_dir_exists": job_dir.exists(),
        "video_exists": video_file.exists(),
        "video_size_kb": round(video_file.stat().st_size / 1024, 1) if video_file.exists() else 0,
        "files": files,
    }
