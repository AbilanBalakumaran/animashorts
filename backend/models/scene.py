from typing import Optional
from pydantic import BaseModel, Field


class Scene(BaseModel):
    id: int
    duration_s: float = Field(..., gt=0)
    visual_prompt: str
    mood: str = "calm"
    image_path: Optional[str] = None


class ScriptOutput(BaseModel):
    narration: str
    scenes: list[Scene]
    total_duration_s: float
    mood: str = "calm"

    @property
    def scene_count(self) -> int:
        return len(self.scenes)
