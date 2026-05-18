"""
Script generation — Groq free tier.
1. llama-3.2-11b-vision analyses each image in depth (subject, setting, mood, details).
2. llama-3.3-70b-versatile writes narration scene-by-scene, one sentence per image.
   A validation pass re-generates any scene whose narration doesn't match its image.
"""

import asyncio
import base64
import io
import json
import os
from pathlib import Path
from dataclasses import dataclass

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from models.job import GenerateRequest
from models.scene import ScriptOutput, Scene

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "script_system.txt").read_text()
_SEM = asyncio.Semaphore(3)   # max 3 concurrent Groq calls


@dataclass
class ImageAnalysis:
    subject: str      # Who/what is the main focus
    setting: str      # Where/context
    mood: str         # Emotional atmosphere
    details: str      # Key visible details (colours, expressions, actions)
    raw: str          # Full description (fallback)

    def to_prompt_block(self, idx: int) -> str:
        return (
            f"Scene {idx + 1} narration MUST describe → Image {idx + 1}:\n"
            f"  Subject  : {self.subject}\n"
            f"  Setting  : {self.setting}\n"
            f"  Mood     : {self.mood}\n"
            f"  Details  : {self.details}\n"
            f"  ↳ Write ONE sentence that specifically references this subject "
            f"in this setting. Do NOT describe any other image."
        )


def _parse_analysis(text: str, fallback: str) -> ImageAnalysis:
    """Parse structured vision output into an ImageAnalysis object."""
    lines = {
        k.strip().upper(): v.strip()
        for line in text.splitlines()
        if ":" in line
        for k, v in [line.split(":", 1)]
    }
    return ImageAnalysis(
        subject=lines.get("SUBJECT", fallback),
        setting=lines.get("SETTING", "unknown setting"),
        mood=lines.get("MOOD", "calm"),
        details=lines.get("DETAILS", ""),
        raw=text,
    )


async def _analyse_image(client: AsyncGroq, image_path: str) -> ImageAnalysis:
    """Deep visual analysis of one image — returns structured metadata."""
    fallback = ImageAnalysis(
        subject="a compelling visual scene",
        setting="unknown setting",
        mood="calm",
        details="",
        raw="",
    )
    try:
        from PIL import Image as PILImage
        img = PILImage.open(image_path).convert("RGB")
        img.thumbnail((768, 768))          # slightly larger → richer vision
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        vision_prompt = (
            "You are analysing a single image for a video narrator. "
            "Identify exactly what is in THIS image and nothing else.\n\n"
            "Answer in this EXACT format (one line each, no extra text):\n"
            "SUBJECT: <who or what is the main focus — be specific, use proper names if visible>\n"
            "SETTING: <location, background, environment>\n"
            "MOOD: <emotional atmosphere: epic | calm | emotional | mysterious | oceanic>\n"
            "DETAILS: <2–3 specific visual details: colours, expressions, objects, symbols>\n\n"
            "Be precise. If you see a specific character, artwork, or place, name it."
        )

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
                        {"type": "text", "text": vision_prompt},
                    ],
                }],
                max_tokens=150,
                temperature=0.1,   # near-deterministic for factual description
            )

        raw = resp.choices[0].message.content.strip()
        analysis = _parse_analysis(raw, Path(image_path).stem)
        print(
            f"[vision] {Path(image_path).name}: "
            f"{analysis.subject} | {analysis.setting} | {analysis.mood}"
        )
        return analysis

    except Exception as e:
        print(f"[vision] failed for {image_path}: {e}")
        return fallback


def _build_user_prompt(req: GenerateRequest, analyses: list[ImageAnalysis]) -> str:
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    n = len(analyses)

    mapping = "\n\n".join(a.to_prompt_block(i) for i, a in enumerate(analyses))

    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"num_images: {n}\n\n"
        f"{'=' * 60}\n"
        f"MANDATORY IMAGE-TO-SCENE MAPPING ({n} scenes, {n} images):\n"
        f"{'=' * 60}\n"
        f"{mapping}\n"
        f"{'=' * 60}\n\n"
        f"Rules:\n"
        f"- Produce EXACTLY {n} scenes.\n"
        f"- Scene N narration describes Image N — never swap.\n"
        f"- Each narration_segment must directly mention the SUBJECT of its image.\n"
        f"- Weave all scenes into a coherent narrative about: {req.topic}"
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


async def _generate_script(
    client: AsyncGroq,
    req: GenerateRequest,
    analyses: list[ImageAnalysis],
) -> dict:
    """Call the text model and return parsed JSON dict."""
    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(req, analyses)},
        ],
        temperature=0.65,
        max_tokens=1200,
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content.strip()
    if "```" in text:
        for part in text.split("```"):
            stripped = part.strip().lstrip("json").strip()
            if stripped.startswith("{"):
                text = stripped
                break
    return json.loads(text)


def _check_scene_match(narration_segment: str, analysis: ImageAnalysis) -> bool:
    """
    Heuristic: the narration should mention at least one key word from the
    image subject or details.  Returns True if it looks correct.
    """
    if not narration_segment or not analysis.subject:
        return True   # can't validate, assume OK

    seg_lower = narration_segment.lower()
    subject_words = [
        w for w in analysis.subject.lower().split()
        if len(w) > 3 and w not in {"with", "that", "this", "from", "have", "been"}
    ]
    detail_words = [
        w for w in analysis.details.lower().split()
        if len(w) > 4 and w not in {"their", "which", "these", "those", "about"}
    ]
    check_words = subject_words[:3] + detail_words[:2]
    return any(w in seg_lower for w in check_words)


async def _fix_mismatched_scenes(
    client: AsyncGroq,
    data: dict,
    analyses: list[ImageAnalysis],
    topic: str,
) -> dict:
    """
    Re-generate any scene whose narration doesn't match its image.
    Only one repair pass to avoid rate-limit loops.
    """
    scenes = data.get("scenes", [])
    repaired = False

    for i, (scene, analysis) in enumerate(zip(scenes, analyses)):
        seg = scene.get("narration_segment", "")
        if not _check_scene_match(seg, analysis):
            print(
                f"[validate] Scene {i + 1} mismatch — "
                f"narration='{seg[:60]}' vs image subject='{analysis.subject}'"
            )
            # Ask the model to fix just this one scene
            fix_prompt = (
                f"The narration for scene {i + 1} is WRONG — it doesn't match its image.\n\n"
                f"Image {i + 1} shows:\n"
                f"  Subject : {analysis.subject}\n"
                f"  Setting : {analysis.setting}\n"
                f"  Details : {analysis.details}\n\n"
                f"Bad narration: \"{seg}\"\n\n"
                f"Write ONE correct replacement sentence (max 15 words) that specifically "
                f"describes this image. Topic context: {topic}.\n"
                f"Reply with ONLY the sentence, no quotes."
            )
            async with _SEM:
                fix_resp = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": fix_prompt}],
                    temperature=0.5,
                    max_tokens=60,
                )
            new_seg = fix_resp.choices[0].message.content.strip().strip('"').strip("'")
            word_count = len(new_seg.split())
            new_duration = round(word_count / 2.5 + 0.5, 1)

            scenes[i]["narration_segment"] = new_seg
            scenes[i]["duration_s"] = new_duration
            print(f"[validate] Scene {i + 1} fixed → '{new_seg}'")
            repaired = True

    if repaired:
        # Rebuild joined narration
        data["narration"] = " ".join(
            s.get("narration_segment", "") for s in scenes
        ).strip()
        data["total_duration_s"] = sum(
            s.get("duration_s", 0) for s in scenes
        )

    return data


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def generate(req: GenerateRequest) -> ScriptOutput:
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

    # Step 1 — deep visual analysis for each image (parallel)
    valid_paths = [p for p in req.image_paths if p and Path(p).exists()]
    if valid_paths:
        results = await asyncio.gather(
            *[_analyse_image(client, p) for p in valid_paths],
            return_exceptions=True,
        )
        analyses: list[ImageAnalysis] = [
            r if isinstance(r, ImageAnalysis) else ImageAnalysis(
                subject="a compelling visual scene",
                setting="unknown", mood="calm", details="", raw="",
            )
            for r in results
        ]
    else:
        analyses = [
            ImageAnalysis(subject="a compelling visual scene",
                          setting="unknown", mood="calm", details="", raw="")
            for _ in req.image_paths or [""]
        ]

    # Step 2 — generate script matched to image analyses
    data = await _generate_script(client, req, analyses)

    # Step 3 — validate each scene narration matches its image; repair if not
    data = await _fix_mismatched_scenes(client, data, analyses, req.topic)

    return _parse_response(
        json.dumps(data),
        req.duration_seconds,
        req.image_paths,
    )
