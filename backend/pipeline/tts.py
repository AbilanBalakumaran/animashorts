"""
TTS — ElevenLabs (primary) with gTTS fallback.
Voice: Adam — deep male, documentary quality (same as InVideo).
"""

import asyncio
import os
import subprocess
from pathlib import Path

from storage.local import narration_path

# ElevenLabs "Adam" — deep documentary male voice
_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
_API_KEY   = os.getenv("ELEVENLABS_API_KEY", "")


def _elevenlabs_sync(text: str, out: Path) -> None:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    client = ElevenLabs(api_key=_API_KEY)
    audio = client.text_to_speech.convert(
        voice_id=_VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.42,
            similarity_boost=0.85,
            style=0.30,
            use_speaker_boost=True,
        ),
    )
    with open(str(out), "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)
    print(f"[TTS] ElevenLabs OK — {out.stat().st_size // 1024} KB")


def _gtts_sync(text: str, out: Path) -> None:
    from gtts import gTTS
    tmp = out.with_suffix(".tmp.mp3")
    gTTS(text=text, lang="en", tld="co.uk", slow=False).save(str(tmp))
    subprocess.run([
        "ffmpeg", "-y", "-i", str(tmp),
        "-af", "equalizer=f=150:width_type=o:width=2:g=4,compand=attacks=0.1:decays=0.3:points=-80/-80|-45/-45|-27/-25|0/-10|20/-7",
        "-ar", "22050", "-b:a", "128k", str(out),
    ], check=True, capture_output=True)
    tmp.unlink(missing_ok=True)


async def synthesize(narration: str, job_id: str) -> Path:
    out = narration_path(job_id)
    loop = asyncio.get_event_loop()

    if _API_KEY:
        try:
            await loop.run_in_executor(None, _elevenlabs_sync, narration, out)
            return out
        except Exception as e:
            print(f"ElevenLabs failed ({e}), falling back to gTTS")

    await loop.run_in_executor(None, _gtts_sync, narration, out)
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
