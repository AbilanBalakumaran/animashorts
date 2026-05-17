from fastapi import APIRouter, HTTPException
from models.job import JobStatus
from api.deps import get_redis

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    r = get_redis()
    raw = r.get(f"job:{job_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus.model_validate_json(raw)
