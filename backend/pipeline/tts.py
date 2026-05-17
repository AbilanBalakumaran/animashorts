"""
TTS — Piper (offline, no API key, documentary-quality male voice).
Model: en_US-ryan-high — deep American male, perfect for anime narration.
"""

import asyncio
import os
import subprocess
import wave
from pathlib import Path

from storage.local import narration_path

_SPEED = float(os.getenv("TTS_SPEED", "0.92"))

# Piper voice config — fully defined here, no env ambiguity
_VOICE_REPO_PATH = "en/en_US/ryan/high/en_US-ryan-high"

_voice = None


def _get_voice():
    global _voice
    if _voice is None:
        from huggingface_hub import hf_hub_download
        from piper.voice import PiperVoice

        model = hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=f"{_VOICE_REPO_PATH}.onnx",
            repo_type="dataset",
        )
        config = hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=f"{_VOICE_REPO_PATH}.onnx.json",
            repo_type="dataset",
        )
        _voice = PiperVoice.load(model, config_path=config, use_cuda=False)
    return _voice


def _synthesize_sync(text: str, out_path: Path) -> None:
    voice = _get_voice()
    wav_path = out_path.with_suffix(".wav")

    with wave.open(str(wav_path), "w") as wf:
        voice.synthesize(
            text,
            wf,
            length_scale=round(1.0 / _SPEED, 3),  # >1 = slower
        )

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path),
         "-codec:a", "libmp3lame", "-b:a", "128k",
         "-ar", "22050",   # reduce sample rate → smaller file
         str(out_path)],
        check=True, capture_output=True,
    )
    wav_path.unlink(missing_ok=True)


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
            segments, _ = model.transcribe(
                str(audio_path), word_timestamps=True, language="en"
            )
            words = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        words.append({"word": w.word, "start": w.start, "end": w.end})
            return words

        return await loop.run_in_executor(None, _run)
    except Exception:
        return []
