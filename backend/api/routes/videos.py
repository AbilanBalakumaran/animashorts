import os
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))

router = APIRouter()


@router.get("/videos")
async def list_videos():
    """List all completed video jobs."""
    videos = []
    if OUTPUT_DIR.exists():
        for job_dir in sorted(OUTPUT_DIR.iterdir(), reverse=True):
            video_file = job_dir / "final_short.mp4"
            if video_file.exists():
                videos.append({
                    "job_id": job_dir.name,
                    "url": f"/outputs/{job_dir.name}/final_short.mp4",
                    "created_at": video_file.stat().st_mtime,
                    "size_mb": round(video_file.stat().st_size / 1_048_576, 2),
                })
    return {"videos": videos}


@router.get("/download/{job_id}")
async def download_video(job_id: str):
    video_file = OUTPUT_DIR / job_id / "final_short.mp4"
    if not video_file.exists():
        return JSONResponse(status_code=404, content={"detail": "Video not found"})
    return FileResponse(
        path=str(video_file),
        media_type="video/mp4",
        filename=f"animashort_{job_id[:8]}.mp4",
    )
