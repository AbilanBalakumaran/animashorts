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
    action: str       # What the subject is DOING (dynamic description)
    setting: str      # Where/context
    mood: str         # Emotional atmosphere
    details: str      # Key visible details (colours, expressions, objects)
    hook: str         # The single most striking / surprising visual element
    raw: str          # Full description (fallback)

    def to_prompt_block(self, idx: int) -> str:
        return (
            f"Scene {idx + 1} narration MUST describe → Image {idx + 1}:\n"
            f"  Subject  : {self.subject}\n"
            f"  Action   : {self.action}\n"
            f"  Setting  : {self.setting}\n"
            f"  Mood     : {self.mood}\n"
            f"  Details  : {self.details}\n"
            f"  Hook     : {self.hook}\n"
            f"  ↳ Write ONE punchy sentence with strong verbs, naming '{self.subject}' "
            f"specifically. Do NOT describe any other image."
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
        action=lines.get("ACTION", "appears"),
        setting=lines.get("SETTING", "unknown setting"),
        mood=lines.get("MOOD", "calm"),
        details=lines.get("DETAILS", ""),
        hook=lines.get("HOOK", ""),
        raw=text,
    )


async def _analyse_image(client: AsyncGroq, image_path: str) -> ImageAnalysis:
    """Deep visual analysis of one image — returns structured metadata."""
    fallback = ImageAnalysis(
        subject="a compelling visual scene",
        action="unfolds",
        setting="unknown setting",
        mood="calm",
        details="",
        hook="",
        raw="",
    )
    try:
        from PIL import Image as PILImage
        img = PILImage.open(image_path).convert("RGB")
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        vision_prompt = (
            "You are analysing a single image for a documentary narrator. "
            "Identify exactly what is in THIS image — nothing else.\n\n"
            "Answer in this EXACT format (one line each, no extra text):\n"
            "SUBJECT: <who or what is the main focus — be very specific, use proper names if visible>\n"
            "ACTION: <what the subject is DOING right now — use active verbs, be specific>\n"
            "SETTING: <location, background, environment>\n"
            "MOOD: <epic | calm | emotional | mysterious | oceanic>\n"
            "DETAILS: <2 key visual details: colours, expressions, symbols, objects, poses>\n"
            "HOOK: <the single most striking or surprising element in this image — 1 short phrase>\n\n"
            "Be precise. If you see a specific character, artwork, or landmark, name it exactly."
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
                max_tokens=200,
                temperature=0.1,   # near-deterministic for factual description
            )

        raw = resp.choices[0].message.content.strip()
        analysis = _parse_analysis(raw, Path(image_path).stem)
        print(
            f"[vision] {Path(image_path).name}: "
            f"{analysis.subject} | {analysis.action} | {analysis.mood}"
        )
        return analysis

    except Exception as e:
        print(f"[vision] failed for {image_path}: {e}")
        return fallback


def _build_user_prompt(req: GenerateRequest, analyses: list[ImageAnalysis]) -> str:
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    n = len(analyses)

    mapping = "\n\n".join(a.to_prompt_block(i) for i, a in enumerate(analyses))

    # Quick-reference table so the LLM can self-check before outputting
    ref_table = "\n".join(
        f"  Scene {i+1} → must name: {a.subject} ({a.action})"
        for i, a in enumerate(analyses)
    )

    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"num_images: {n}\n\n"
        f"{'=' * 60}\n"
        f"MANDATORY IMAGE-TO-SCENE MAPPING ({n} scenes, {n} images):\n"
        f"{'=' * 60}\n"
        f"{mapping}\n"
        f"{'=' * 60}\n\n"
        f"RULES:\n"
        f"- Produce EXACTLY {n} scenes.\n"
        f"- Scene N narration describes Image N — never swap.\n"
        f"- Use strong verbs and vivid language — make each sentence feel cinematic.\n"
        f"- Weave all scenes into a coherent narrative about: {req.topic}\n\n"
        f"QUICK-CHECK TABLE (verify before outputting):\n"
        f"{ref_table}"
    )


def _build_user_prompt_no_images(req: GenerateRequest) -> str:
    """User prompt for the AI-generates-images mode — no uploaded images."""
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    # Estimate scene count: ~4s per scene, min 2, max 12
    n = max(2, min(12, req.duration_seconds // 4))

    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"Create EXACTLY {n} scenes.\n\n"
        f"For each scene:\n"
        f"1. narration_segment — 1 punchy sentence with strong verbs, cinematic tone\n"
        f"2. visual_prompt — describe the perfect anime image to show during this sentence:\n"
        f"   - Name the specific character or subject shown\n"
        f"   - Describe what they are doing\n"
        f"   - Include 'One Piece anime style' or relevant style tag\n"
        f"   Example: 'Eiichiro Oda drawing at desk night lamp One Piece anime style'\n"
        f"   Example: 'Jinbei fishman warrior underwater ocean One Piece anime style'\n\n"
        f"Word budget: ~{req.duration_seconds // 2} words total across all narration segments.\n"
        f"Use strong verbs. Open scene 1 with a hook. Tell a compelling story about: {req.topic}"
    )


def _duration_from_text(text: str, fallback: float) -> float:
    """
    Compute scene duration from the actual narration text.
    Formula: word_count / 2.5 + 0.5  (2.5 words/sec documentary pace + 0.5s pause)
    Never trust the LLM's own duration calculation — it often multiplies instead of divides.
    """
    if not text or not text.strip():
        return max(fallback, 1.5)
    word_count = len(text.split())
    return max(round(word_count / 2.5 + 0.5, 2), 1.5)


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
        while len(scenes_raw) < num_images:
            scenes_raw.append({
                "id": len(scenes_raw) + 1,
                "mood": data.get("mood", "calm"),
                "narration_segment": "",
            })
    elif len(scenes_raw) > num_images:
        scenes_raw = scenes_raw[:num_images]

    scenes = []
    for i, s in enumerate(scenes_raw):
        seg = s.get("narration_segment", "")
        # Always recompute duration from actual word count — never trust LLM math
        dur = _duration_from_text(seg, duration / num_images)
        scenes.append(Scene(
            id=s.get("id", i + 1),
            duration_s=dur,
            mood=s.get("mood", "calm"),
            image_path=image_paths[i] if i < len(image_paths) else None,
            visual_prompt=s.get("visual_prompt", ""),
        ))

    total = sum(sc.duration_s for sc in scenes)

    # Safety cap: if total is more than 40% over the requested duration, scale down
    max_allowed = duration * 1.4
    if total > max_allowed:
        scale = max_allowed / total
        print(f"[script] duration {total:.1f}s > cap {max_allowed:.1f}s — scaling by {scale:.2f}")
        for sc in scenes:
            sc.duration_s = max(round(sc.duration_s * scale, 2), 1.5)
        total = sum(sc.duration_s for sc in scenes)

    return ScriptOutput(
        narration=data["narration"],
        scenes=scenes,
        total_duration_s=round(total, 2),
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
                f"  Action  : {analysis.action}\n"
                f"  Setting : {analysis.setting}\n"
                f"  Hook    : {analysis.hook}\n"
                f"  Details : {analysis.details}\n\n"
                f"Bad narration: \"{seg}\"\n\n"
                f"Write ONE punchy replacement sentence (max 15 words) that names '{analysis.subject}' "
                f"and uses strong verbs. Topic context: {topic}.\n"
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
            new_duration = _duration_from_text(new_seg, 3.0)

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

    valid_paths = [p for p in (req.image_paths or []) if p and Path(p).exists()]

    if valid_paths:
        # ── Mode A: user uploaded images ──────────────────────────────────────
        # Step 1 — deep visual analysis for each image (parallel)
        results = await asyncio.gather(
            *[_analyse_image(client, p) for p in valid_paths],
            return_exceptions=True,
        )
        analyses: list[ImageAnalysis] = [
            r if isinstance(r, ImageAnalysis) else ImageAnalysis(
                subject="a compelling visual scene",
                action="unfolds",
                setting="unknown", mood="calm", details="", hook="", raw="",
            )
            for r in results
        ]

        # Step 2 — generate script matched to image analyses
        data = await _generate_script(client, req, analyses)

        # Step 3 — repair any scenes whose narration doesn't match their image
        data = await _fix_mismatched_scenes(client, data, analyses, req.topic)

        return _parse_response(json.dumps(data), req.duration_seconds, valid_paths)

    else:
        # ── Mode B: no images uploaded — AI generates everything ──────────────
        # Ask LLM to create narration + visual_prompt per scene (no image analysis)
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": _build_user_prompt_no_images(req)},
            ],
            temperature=0.7,
            max_tokens=1400,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        if "```" in text:
            for part in text.split("```"):
                stripped = part.strip().lstrip("json").strip()
                if stripped.startswith("{"):
                    text = stripped
                    break
        data = json.loads(text)

        # No image_paths — scenes get None image_path (image_gen will fill them)
        return _parse_response(json.dumps(data), req.duration_seconds, [])
