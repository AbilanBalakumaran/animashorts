"""
Script generation — uses Groq (free tier).
Model: llama-3.3-70b-versatile
Generates narration + scene timing for user-uploaded images.
"""

import json
import os
from pathlib import Path

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from models.job import GenerateRequest
from models.scene import ScriptOutput, Scene

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "script_system.txt").read_text()


def _build_user_prompt(req: GenerateRequest) -> str:
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    num_images = max(len(req.image_paths), 1)
    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"num_images: {num_images}\n"
        "Generate the script JSON now."
    )


def _parse_response(text: str, duration: int, image_paths: list[str]) -> ScriptOutput:
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            stripped = part.strip().lstrip("json").strip()
            if stripped.startswith("{"):
                text = stripped
                break
    data = json.loads(text)

    scenes_raw = data.get("scenes", [])
    # Assign uploaded image paths to scenes
    scenes = []
    for i, s in enumerate(scenes_raw):
        img = image_paths[i] if i < len(image_paths) else None
        scenes.append(Scene(
            id=s.get("id", i + 1),
            duration_s=float(s.get("duration_s", duration / max(len(scenes_raw), 1))),
            mood=s.get("mood", "calm"),
            image_path=img,
        ))

    return ScriptOutput(
        narration=data["narration"],
        scenes=scenes,
        total_duration_s=float(data.get("total_duration_s", duration)),
        mood=data.get("mood", "calm"),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def generate(req: GenerateRequest) -> ScriptOutput:
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(req)},
        ],
        temperature=0.75,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )

    return _parse_response(resp.choices[0].message.content, req.duration_seconds, req.image_paths)
