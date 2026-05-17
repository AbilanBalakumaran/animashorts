"""
Script generation — uses Groq (free tier).
Model: llama-3.3-70b-versatile
Free limits: 30 req/min, 14 400 req/day — largement suffisant.
Compte gratuit: https://console.groq.com (pas de CB requise)
"""

import json
import os
from pathlib import Path

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from models.job import GenerateRequest
from models.scene import ScriptOutput, Scene

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "script_system.txt").read_text()

STYLE_MODIFIERS = {
    "oceanic":     "deep ocean setting, flowing water, glowing blue hues, bioluminescent light",
    "epic":        "dramatic battle composition, intense lighting, dynamic action pose",
    "mysterious":  "dark atmospheric fog, moonlight, silhouettes, deep purple tones",
    "emotional":   "soft golden hour lighting, tearful expression, gentle wind, warm tones",
    "documentary": "clean composition, neutral tones, thoughtful expression, wide establishing shot",
    "manga":       "black and white manga panels, speed lines, heavy ink contrast",
}


def _build_user_prompt(req: GenerateRequest) -> str:
    style_mod = STYLE_MODIFIERS.get(req.style, STYLE_MODIFIERS["oceanic"])
    hint = f"\nNarration hint: {req.script_hint}" if req.script_hint else ""
    return (
        f"Topic: {req.topic}{hint}\n"
        f"Target duration: {req.duration_seconds} seconds\n"
        f"Visual style: {req.style} — {style_mod}\n"
        "Generate the script JSON now."
    )


def _parse_response(text: str, duration: int) -> ScriptOutput:
    text = text.strip()
    # Strip markdown code fences if present
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                text = stripped
                break
    data = json.loads(text)
    scenes = [Scene(**s) for s in data["scenes"]]
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

    return _parse_response(resp.choices[0].message.content, req.duration_seconds)
