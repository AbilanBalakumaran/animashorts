"""
TTS — gTTS (Google Text-to-Speech) via HTTP.
100% gratuit, pas de WebSocket, fonctionne sur HuggingFace Spaces.
"""

import asyncio
import os
from pathlib import Path

from storage.local import narration_path

DEFAULT_LANG = os.getenv("TTS_LANG", "en")
DEFAULT_TLD  = os.getenv("TTS_TLD", "com")   # 'co.uk' for British accent


async def _gtts_synthesize(text: str, job_id: str) -> Path:
    from gtts import gTTS

    out = narration_path(job_id)

    loop = asyncio.get_event_loop()

    def _run():
        tts = gTTS(text=text, lang=DEFAULT_LANG, tld=DEFAULT_TLD, slow=False)
        tts.save(str(out))

    await loop.run_in_executor(None, _run)
    return out


async def get_word_timestamps(audio_path: Path) -> list[dict]:
    """Extrait les timestamps via faster-whisper (local, gratuit)."""
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


async def synthesize(narration: str, job_id: str) -> Path:
    return await _gtts_synthesize(narration, job_id)
