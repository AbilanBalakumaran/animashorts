from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.deps import get_redis
from models.job import GenerateRequest, GenerateResponse, JobStatus
from pipeline.orchestrator import run_pipeline
from storage.local import job_dir

router = APIRouter()

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024   # 20 MB per image
MAX_TOTAL_BYTES = 150 * 1024 * 1024  # 150 MB total
# JPEG/PNG/WebP magic bytes
_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG":      "image/png",
    b"RIFF":         "image/webp",  # WebP starts with RIFF
}


def _validate_image_bytes(data: bytes) -> bool:
    for magic in _MAGIC:
        if data[:len(magic)] == magic:
            return True
    return False


@router.post("/generate", response_model=GenerateResponse)
async def generate_video(
    topic: str = Form(...),
    script_hint: Optional[str] = Form(None),
    style: str = Form("oceanic"),
    duration_seconds: int = Form(16),
    subtitles: bool = Form(False),
    images: List[UploadFile] = File(...),
):
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(images) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 images allowed")

    status = JobStatus.create()
    d = job_dir(status.job_id)

    image_paths: list[str] = []
    total_bytes = 0

    for i, img in enumerate(images):
        data = await img.read()
        total_bytes += len(data)

        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail=f"Image {i+1} exceeds 20 MB limit")
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=400, detail="Total upload size exceeds 150 MB")
        if not _validate_image_bytes(data):
            raise HTTPException(status_code=400, detail=f"File {i+1} is not a valid image")

        suffix = Path(img.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            suffix = ".jpg"
        dest = d / f"upload_{i:02d}{suffix}"
        dest.write_bytes(data)
        image_paths.append(str(dest))

    req = GenerateRequest(
        topic=topic,
        script_hint=script_hint,
        style=style,
        duration_seconds=duration_seconds,
        subtitles=subtitles,
        image_paths=image_paths,
    )

    r = get_redis()
    r.set(f"job:{status.job_id}", status.model_dump_json(), ex=86400)

    run_pipeline.apply_async(
        args=[status.job_id, req.model_dump()],
        queue="video_pipeline",
    )

    return GenerateResponse(job_id=status.job_id)
