from typing import Optional
from pydantic import BaseModel, Field


class Scene(BaseModel):
    id: int
    duration_s: float = Field(..., gt=0)
    mood: str = "calm"
    image_path: Optional[str] = None
    visual_prompt: str = ""  # kept for backward compat, unused with user images


class ScriptOutput(BaseModel):
    narration: str
    scenes: list[Scene]
    total_duration_s: float
    mood: str = "calm"

    @property
    def scene_count(self) -> int:
        return len(self.scenes)
