"""
Script generation — Groq free tier.
1. llama-3.2-11b-vision describes each uploaded image (parallel).
2. llama-3.3-70b-versatile writes narration that matches each image.
"""

import asyncio
import base64
import io
import json
import os
from pathlib import Path

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from models.job import GenerateRequest
from models.scene import ScriptOutput, Scene

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "script_system.txt").read_text()
_SEM = asyncio.Semaphore(3)   # max 3 concurrent vision calls


async def _describe_image(client: AsyncGroq, image_path: str) -> str:
    """Send a thumbnail to Groq vision and get a one-sentence description."""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(image_path).convert("RGB")
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        async with _SEM:
            resp = await client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describe the main subject, setting, and mood of this image "
                                "in ONE vivid sentence (max 20 words). "
                                "Focus on what a documentary narrator would highlight."
                            ),
                        },
                    ],
                }],
                max_tokens=80,
                temperature=0.3,
            )
        desc = resp.choices[0].message.content.strip().strip('"')
        print(f"[vision] {Path(image_path).name}: {desc}")
        return desc
    except Exception as e:
        print(f"[vision] failed for {image_path}: {e}")
        return "a compelling scene"


def _build_user_prompt(req: GenerateRequest, descriptions: list[str]) -> str:
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    n = len(descriptions)
    mapping_lines = "\n".join(
        f"  Scene {i + 1} narration → MUST be about → Image {i + 1}: {d}"
        for i, d in enumerate(descriptions)
    )
    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"num_images: {n}\n\n"
        f"MANDATORY SCENE-TO-IMAGE MAPPING (Scene N = Image N, no exceptions):\n"
        f"{mapping_lines}\n\n"
        f"Generate exactly {n} scenes. "
        f"Scene 1 narration describes Image 1. Scene 2 narration describes Image 2. "
        f"And so on — do NOT swap or reorder."
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

    if len(scenes_raw) < num_images:
        per_scene = duration / num_images
        while len(scenes_raw) < num_images:
            scenes_raw.append({
                "id": len(scenes_raw) + 1,
                "duration_s": per_scene,
                "mood": data.get("mood", "calm"),
            })
    elif len(scenes_raw) > num_images:
        excess = sum(s.get("duration_s", 0) for s in scenes_raw[num_images:])
        scenes_raw = scenes_raw[:num_images]
        scenes_raw[-1]["duration_s"] = scenes_raw[-1].get("duration_s", 0) + excess

    scenes = [
        Scene(
            id=s.get("id", i + 1),
            duration_s=max(float(s.get("duration_s", duration / num_images)), 1.5),
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

    # Step 1 — describe each image in parallel
    valid_paths = [p for p in req.image_paths if p and Path(p).exists()]
    if valid_paths:
        results = await asyncio.gather(
            *[_describe_image(client, p) for p in valid_paths],
            return_exceptions=True,
        )
        descriptions = [
            r if isinstance(r, str) else "a compelling visual scene"
            for r in results
        ]
    else:
        descriptions = ["a compelling visual scene"] * max(len(req.image_paths), 1)

    # Step 2 — generate narration script matched to image descriptions
    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(req, descriptions)},
        ],
        temperature=0.75,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )

    return _parse_response(
        resp.choices[0].message.content,
        req.duration_seconds,
        req.image_paths,
    )
