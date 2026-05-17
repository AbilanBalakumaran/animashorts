"""
TTS — edge-tts (Microsoft Edge neural voices).
100% gratuit, aucun compte, aucune clé API.
Qualité équivalente à Azure Neural TTS.

Voix disponibles (anglais, style documentaire) :
  en-US-GuyNeural        — voix masculine calme, parfaite pour narration
  en-US-ChristopherNeural — voix masculine grave, cinématique
  en-US-AriaNeural       — voix féminine douce

Timestamps extraits via faster-whisper (local, 100% gratuit).
"""

import asyncio
import os
import subprocess
from pathlib import Path

import aiofiles
import edge_tts
from tenacity import retry, stop_after_attempt, wait_exponential

from storage.local import narration_path

# Voix par défaut — calme, documentaire
DEFAULT_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")
DEFAULT_RATE  = os.getenv("EDGE_TTS_RATE",  "-8%")   # légèrement plus lent = plus cinématique
DEFAULT_PITCH = os.getenv("EDGE_TTS_PITCH", "-5Hz")  # légèrement plus grave


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def _edge_synthesize(text: str, job_id: str) -> Path:
    out = narration_path(job_id)
    communicate = edge_tts.Communicate(
        text,
        voice=DEFAULT_VOICE,
        rate=DEFAULT_RATE,
        pitch=DEFAULT_PITCH,
    )
    await communicate.save(str(out))
    return out


async def get_word_timestamps(audio_path: Path) -> list[dict]:
    """Extrait les timestamps par mot via faster-whisper (local, 100% gratuit)."""
    try:
        from faster_whisper import WhisperModel

        loop = asyncio.get_event_loop()

        def _run():
            model = WhisperModel(
                "tiny",           # modèle le plus léger, rapide sur CPU
                device="cpu",
                compute_type="int8",
            )
            segments, _ = model.transcribe(
                str(audio_path),
                word_timestamps=True,
                language="en",
            )
            words = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word":  w.word,
                            "start": w.start,
                            "end":   w.end,
                        })
            return words

        return await loop.run_in_executor(None, _run)
    except Exception:
        return []


async def synthesize(narration: str, job_id: str) -> Path:
    return await _edge_synthesize(narration, job_id)
