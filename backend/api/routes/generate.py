from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.deps import get_redis
from models.job import GenerateRequest, GenerateResponse, JobStatus
from pipeline.orchestrator import run_pipeline
from storage.local import job_dir

router = APIRouter()

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


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
    for i, img in enumerate(images):
        suffix = Path(img.filename or "").suffix.lower() or ".jpg"
        if suffix not in ALLOWED_SUFFIXES:
            suffix = ".jpg"
        dest = d / f"upload_{i:02d}{suffix}"
        dest.write_bytes(await img.read())
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
