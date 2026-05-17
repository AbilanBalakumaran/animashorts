import asyncio
import os
import subprocess
from pathlib import Path
from storage.local import narration_path


async def synthesize(narration: str, job_id: str) -> Path:
    out = narration_path(job_id)
    loop = asyncio.get_event_loop()

    def _run():
        from gtts import gTTS
        tts = gTTS(text=narration, lang="en", tld="co.uk", slow=False)
        mp3 = out.with_suffix(".tmp.mp3")
        tts.save(str(mp3))
        # Bass boost + slight compression to reduce robotic feel
        subprocess.run([
            "ffmpeg", "-y", "-i", str(mp3),
            "-af", "equalizer=f=150:width_type=o:width=2:g=4,compand=attacks=0.1:decays=0.3:points=-80/-80|-45/-45|-27/-25|0/-10|20/-7",
            "-ar", "22050", "-b:a", "128k",
            str(out)
        ], check=True, capture_output=True)
        mp3.unlink(missing_ok=True)

    await loop.run_in_executor(None, _run)
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
