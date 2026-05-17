"""
Subtitle generation stage.
Produces an SRT file from Whisper word timestamps.
"""

from pathlib import Path
from storage.local import subtitles_path


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunk_words(words: list[dict], max_chars: int = 35) -> list[dict]:
    """Group words into subtitle chunks of max_chars."""
    chunks = []
    current_words = []
    current_text = ""

    for w in words:
        word_text = w.get("word", "")
        if len(current_text) + len(word_text) + 1 > max_chars and current_words:
            chunks.append({
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "text": current_text.strip(),
            })
            current_words = []
            current_text = ""
        current_words.append(w)
        current_text += " " + word_text

    if current_words:
        chunks.append({
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
            "text": current_text.strip(),
        })
    return chunks


def generate_srt(words: list[dict], job_id: str) -> Path | None:
    if not words:
        return None

    chunks = _chunk_words(words)
    lines = []
    for i, chunk in enumerate(chunks, 1):
        start = _format_time(chunk["start"])
        end = _format_time(chunk["end"])
        lines.append(f"{i}\n{start} --> {end}\n{chunk['text']}\n")

    srt_content = "\n".join(lines)
    out = subtitles_path(job_id)
    out.write_text(srt_content, encoding="utf-8")
    return out
