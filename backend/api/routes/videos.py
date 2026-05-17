import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))

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
async def stream_video(job_id: str, request: Request):
    """Serve video with full Range-request support for browser <video> elements."""
    video_file = _video_path(job_id)
    if not video_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    file_size = video_file.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        # Parse "bytes=start-end"
        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
        except Exception:
            raise HTTPException(status_code=416, detail="Invalid Range header")

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_file():
            with open(video_file, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = f.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Cache-Control": "no-cache",
            },
        )

    # Full file
    return FileResponse(
        path=str(video_file),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "no-cache",
        },
    )


@router.get("/download/{job_id}")
async def download_video(job_id: str):
    video_file = _video_path(job_id)
    if not video_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(
        path=str(video_file),
        media_type="video/mp4",
        filename=f"animashort_{job_id[:8]}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )
