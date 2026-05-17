"""
Génération d'images — HuggingFace Inference API (gratuit).
Compte gratuit: https://huggingface.co (pas de CB)
Token HF: https://huggingface.co/settings/tokens

Modèles utilisés (anime, gratuits) :
  Primary  : Linaqruf/animagine-xl-3.1   (SDXL anime haute qualité)
  Fallback : stablediffusionapi/anything-v5 (anime classique)
  Fallback2: placeholder couleur unie si tout échoue

Sans GPU — fonctionne en inference API HuggingFace.
Avec GPU local — décommentez la section diffusers.
"""

import asyncio
import os
import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from models.scene import Scene
from storage.local import image_path

NEGATIVE_PROMPT = (
    "realistic, 3D render, photography, photo, blurry, watermark, text, "
    "signature, ugly, deformed, low quality, nsfw, bad anatomy, extra limbs"
)

HF_API_URL = "https://api-inference.huggingface.co/models/{model}"

HF_ANIME_MODELS = [
    "Linaqruf/animagine-xl-3.1",
    "cagliostrolab/animagine-xl-3.1",
    "stablediffusionapi/anything-v5",
]


def _anime_enhance(prompt: str, style: str = "oceanic") -> str:
    base = (
        f"{prompt}, anime style, cel shaded, high quality illustration, "
        "detailed linework, vibrant colors, masterpiece, best quality"
    )
    return base


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=20))
async def _hf_generate(prompt: str, scene: Scene, job_id: str, model: str) -> Path:
    token = os.getenv("HF_API_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    enhanced = _anime_enhance(prompt)
    payload = {
        "inputs": enhanced,
        "parameters": {
            "negative_prompt": NEGATIVE_PROMPT,
            "width": 768,
            "height": 1344,
            "num_inference_steps": 25,
            "guidance_scale": 7.5,
        },
        "options": {"wait_for_model": True},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            HF_API_URL.format(model=model),
            headers=headers,
            json=payload,
        )
        if resp.status_code == 503:
            # Model loading — wait and retry
            await asyncio.sleep(20)
            raise RuntimeError("Model loading, retrying...")
        resp.raise_for_status()
        image_bytes = resp.content

    # Vérifier que c'est bien une image (pas un JSON d'erreur)
    if image_bytes[:4] not in (b"\x89PNG", b"\xff\xd8\xff", b"RIFF"):
        raise RuntimeError(f"Response is not an image: {image_bytes[:100]}")

    out = image_path(job_id, scene.id)
    out.write_bytes(image_bytes)
    return out


async def _generate_with_fallbacks(scene: Scene, job_id: str) -> Scene:
    for model in HF_ANIME_MODELS:
        try:
            path = await _hf_generate(scene.visual_prompt, scene, job_id, model)
            scene.image_path = str(path)
            return scene
        except Exception:
            continue

    # Dernier recours : image placeholder colorée
    scene.image_path = str(await _create_placeholder(scene.id, scene.mood, job_id))
    return scene


async def _create_placeholder(scene_id: int, mood: str, job_id: str) -> Path:
    """Crée une image de couleur unie si la génération échoue."""
    from PIL import Image, ImageDraw, ImageFont

    MOOD_COLORS = {
        "oceanic":     (15, 52, 96),
        "epic":        (80, 10, 10),
        "mysterious":  (20, 0, 40),
        "emotional":   (80, 40, 0),
        "calm":        (20, 40, 60),
        "documentary": (30, 30, 30),
    }
    MOOD_ACCENT = {
        "oceanic":     (0, 200, 255),
        "epic":        (255, 80, 0),
        "mysterious":  (150, 0, 255),
        "emotional":   (255, 180, 0),
        "calm":        (100, 180, 255),
        "documentary": (180, 180, 180),
    }

    bg    = MOOD_COLORS.get(mood, (20, 20, 30))
    color = MOOD_ACCENT.get(mood, (100, 100, 200))

    img  = Image.new("RGB", (768, 1344), color=bg)
    draw = ImageDraw.Draw(img)

    # Cercle lumineux au centre
    cx, cy, r = 384, 672, 120
    for i in range(r, 0, -1):
        alpha = int(80 * (1 - i / r))
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*color, alpha))

    draw.text((384, 672), f"Scene {scene_id}", fill=color, anchor="mm")

    out = image_path(job_id, scene_id)
    img.save(str(out), "PNG")
    return out


async def generate_scenes(scenes: list[Scene], job_id: str) -> list[Scene]:
    """Génère toutes les images en parallèle."""
    return list(await asyncio.gather(*[
        _generate_with_fallbacks(s, job_id) for s in scenes
    ]))
