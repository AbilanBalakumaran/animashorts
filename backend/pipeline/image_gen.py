"""
AI image generation using Pollinations.ai — free, no API key required.
Used when the user chooses "AI generates images" mode (no upload).

API: GET https://image.pollinations.ai/prompt/{prompt}?...
Returns a JPEG image directly. Powered by FLUX.

Pollinations is free and open — no account, no API key, no rate limit (be reasonable).
Docs: https://pollinations.ai
"""

import asyncio
from pathlib import Path
from urllib.parse import quote

import httpx

from models.scene import Scene

# 9:16 portrait — clean resolution for vertical shorts
_IMG_W = 768
_IMG_H = 1365

# Appended to every prompt for consistent anime style output
_STYLE_SUFFIX = (
    "One Piece anime style cel shaded detailed illustration "
    "cinematic vertical portrait dramatic lighting vibrant colors "
    "masterpiece studio quality no watermark no text no logo"
)

# Negative elements included via prompt phrasing (Pollinations uses prompt-based neg)
_NEG = "avoid realistic photography 3D render blurry watermark"

# Max 2 concurrent requests to Pollinations (polite usage)
_SEM = asyncio.Semaphore(2)


def _build_prompt(scene: Scene, topic: str) -> str:
    """Build the full image generation prompt for a scene."""
    base = (scene.visual_prompt or f"{topic} anime scene").strip().rstrip(".,;:")
    return f"{base}, {_STYLE_SUFFIX}"


async def _fetch_image(prompt: str, out: Path, seed: int) -> Path:
    """Download one image from Pollinations.ai."""
    url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width={_IMG_W}&height={_IMG_H}"
        f"&nologo=true&seed={seed}&model=flux&enhance=true"
    )
    async with _SEM:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content

    # Validate it's an image, not an error JSON
    if content[:4] not in (b"\x89PNG", b"\xff\xd8\xff", b"RIFF", b"ftyp"):
        if len(content) < 1000:
            raise RuntimeError(f"Pollinations returned non-image: {content[:200]}")

    out.write_bytes(content)
    return out


async def _placeholder(out: Path, mood: str, scene_id: int) -> Path:
    """Solid-colour fallback image if Pollinations fails."""
    from PIL import Image, ImageDraw

    COLORS = {
        "oceanic":    (15, 52, 96),
        "epic":       (60, 10, 10),
        "mysterious": (20, 0, 40),
        "emotional":  (70, 30, 0),
        "calm":       (20, 40, 60),
    }
    ACCENTS = {
        "oceanic":    (0, 200, 255),
        "epic":       (255, 80, 0),
        "mysterious": (150, 0, 255),
        "emotional":  (255, 160, 0),
        "calm":       (100, 180, 255),
    }
    bg = COLORS.get(mood, (20, 20, 30))
    ac = ACCENTS.get(mood, (120, 120, 200))
    img = Image.new("RGB", (_IMG_W, _IMG_H), color=bg)
    draw = ImageDraw.Draw(img)
    cx, cy, r = _IMG_W // 2, _IMG_H // 2, 100
    for i in range(r, 0, -4):
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=ac)
    draw.text((cx, cy), f"Scene {scene_id}", fill=(255, 255, 255), anchor="mm")
    img.save(str(out), "JPEG", quality=90)
    return out


async def generate_for_scenes(
    scenes: list[Scene],
    topic: str,
    job_id: str,
) -> list[Scene]:
    """
    Generate one AI image per scene that has no image_path yet.
    Modifies scenes in-place and returns the updated list.
    """
    from storage.local import job_dir
    d = job_dir(job_id)

    async def _process(i: int, scene: Scene) -> None:
        if scene.image_path and Path(scene.image_path).exists():
            return  # user-uploaded image — skip

        prompt = _build_prompt(scene, topic)
        out = d / f"ai_image_{i:02d}.jpg"
        seed = i * 13 + 7  # different seed per scene for variety

        print(f"[image_gen] generating scene {i+1}: {prompt[:80]}…")
        try:
            await _fetch_image(prompt, out, seed)
            scene.image_path = str(out)
            print(f"[image_gen] scene {i+1} ✓  ({out.stat().st_size // 1024} KB)")
        except Exception as exc:
            print(f"[image_gen] scene {i+1} FAILED ({exc}) — using placeholder")
            fallback = d / f"placeholder_{i:02d}.jpg"
            await _placeholder(fallback, scene.mood, scene.id)
            scene.image_path = str(fallback)

    await asyncio.gather(*[_process(i, s) for i, s in enumerate(scenes)])
    return scenes
