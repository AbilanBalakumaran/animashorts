"""
TTS — Kokoro-82M ONNX (offline, no API key, documentary-quality voice).
Voice: am_adam — deep American male, perfect for anime documentary narration.
"""

import asyncio
import os
from pathlib import Path

from storage.local import narration_path

VOICE = os.getenv("TTS_VOICE", "am_adam")   # deep male documentary voice
SPEED = float(os.getenv("TTS_SPEED", "0.92"))  # slightly slower = more cinematic

_kokoro = None


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        from huggingface_hub import hf_hub_download
        model_path  = hf_hub_download("hexgrad/Kokoro-82M-ONNX", "kokoro-v1.0.onnx")
        voices_path = hf_hub_download("hexgrad/Kokoro-82M-ONNX", "voices-v1.0.bin")
        _kokoro = Kokoro(model_path, voices_path)
    return _kokoro


def _synthesize_sync(text: str, out_path: Path) -> None:
    import numpy as np
    import soundfile as sf

    kokoro = _get_kokoro()
    samples, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
    sf.write(str(out_path), samples, sr)


async def synthesize(narration: str, job_id: str) -> Path:
    out = narration_path(job_id)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _synthesize_sync, narration, out)
    return out


async def get_word_timestamps(audio_path: Path) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
        loop = asyncio.get_event_loop()

        def _run():
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(audio_path), word_timestamps=True, language="en")
            words = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        words.append({"word": w.word, "start": w.start, "end": w.end})
            return words

        return await loop.run_in_executor(None, _run)
    except Exception:
        return []
