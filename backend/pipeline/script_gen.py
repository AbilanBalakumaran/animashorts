"""
Script generation — Groq free tier (llama-3.3-70b-versatile).
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
    num_images = len(image_paths)

    # Guard: always produce exactly one scene per image
    if len(scenes_raw) < num_images:
        # Pad missing scenes by splitting duration equally
        per_scene = duration / num_images
        while len(scenes_raw) < num_images:
            scenes_raw.append({
                "id": len(scenes_raw) + 1,
                "duration_s": per_scene,
                "mood": data.get("mood", "calm"),
            })
    elif len(scenes_raw) > num_images:
        # Merge excess scenes into last one
        excess_duration = sum(s.get("duration_s", 0) for s in scenes_raw[num_images:])
        scenes_raw = scenes_raw[:num_images]
        scenes_raw[-1]["duration_s"] = scenes_raw[-1].get("duration_s", 0) + excess_duration

    scenes = [
        Scene(
            id=s.get("id", i + 1),
            duration_s=max(float(s.get("duration_s", duration / num_images)), 1.0),
            mood=s.get("mood", "calm"),
            image_path=image_paths[i],
        )
        for i, s in enumerate(scenes_raw)
    ]

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
