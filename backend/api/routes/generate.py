from fastapi import APIRouter, HTTPException
from models.job import GenerateRequest, GenerateResponse, JobStatus
from api.deps import get_redis
from pipeline.orchestrator import run_pipeline

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate_video(req: GenerateRequest):
    status = JobStatus.create()
    r = get_redis()
    r.set(f"job:{status.job_id}", status.model_dump_json(), ex=86400)

    run_pipeline.apply_async(
        args=[status.job_id, req.model_dump()],
        queue="video_pipeline",
    )

    return GenerateResponse(job_id=status.job_id)
