from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import time
import uuid


class JobStep(str, Enum):
    queued = "queued"
    script = "script"
    tts = "tts"
    images = "images"
    render = "render"
    done = "done"
    error = "error"


STEP_PROGRESS = {
    JobStep.queued: 0,
    JobStep.script: 10,
    JobStep.tts: 25,
    JobStep.images: 45,
    JobStep.render: 75,
    JobStep.done: 100,
    JobStep.error: 0,
}

STEP_LABELS = {
    JobStep.queued: "Queued",
    JobStep.script: "Writing script...",
    JobStep.tts: "Generating voice-over...",
    JobStep.images: "Generating anime visuals...",
    JobStep.render: "Rendering video...",
    JobStep.done: "Complete!",
    JobStep.error: "Failed",
}


class JobStatus(BaseModel):
    job_id: str
    step: JobStep = JobStep.queued
    progress: int = 0
    label: str = "Queued"
    output_url: Optional[str] = None
    error: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @classmethod
    def create(cls) -> "JobStatus":
        job_id = str(uuid.uuid4())
        return cls(job_id=job_id)

    def advance(self, step: JobStep, error: str | None = None) -> "JobStatus":
        self.step = step
        self.progress = STEP_PROGRESS[step]
        self.label = STEP_LABELS[step]
        self.updated_at = time.time()
        if error:
            self.error = error
        return self


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500, description="Main topic or subject")
    script_hint: Optional[str] = Field(None, max_length=1000, description="Optional script idea or narration hint")
    style: str = Field("oceanic", description="Visual style preset")
    duration_seconds: int = Field(16, ge=10, le=60, description="Target video duration in seconds")
    subtitles: bool = Field(False, description="Burn subtitles into video")


class GenerateResponse(BaseModel):
    job_id: str
    message: str = "Video generation started"
