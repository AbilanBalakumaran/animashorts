"""
Video rendering — MoviePy + FFmpeg.
Uses simple dezoom (progressive zoom-out) on user-supplied images.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from models.job import GenerateRequest
from models.scene import Scene, ScriptOutput
from storage.local import output_video_path, subtitles_path

VIDEO_W = int(os.getenv("VIDEO_WIDTH", 1080))
VIDEO_H = int(os.getenv("VIDEO_HEIGHT", 1920))
FPS = int(os.getenv("VIDEO_FPS", 24))
BGM_VOLUME = 0.12


def _load_image(path: Optional[str]) -> np.ndarray:
    if not path or not Path(path).exists():
        return np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
    img = Image.open(path).convert("RGB")
    # Crop to 9:16 (fill, not letterbox)
    src_w, src_h = img.size
    target_ratio = VIDEO_W / VIDEO_H
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))
    img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    return np.array(img)


def _dezoom_frame(img: np.ndarray, t: float, duration: float, direction: int) -> np.ndarray:
    """Progressive dezoom: start zoomed in (1.15x), end at normal (1.0x)."""
    h, w = img.shape[:2]
    progress = t / max(duration, 0.001)

    # Dezoom: zoom decreases from 1.15 to 1.0
    zoom = 1.15 - 0.15 * progress
    crop_w = int(w / zoom)
    crop_h = int(h / zoom)

    max_x = w - crop_w
    max_y = h - crop_h

    if direction == 0:  # pan right → center
        x = int(max_x * (1 - progress * 0.5))
        y = max_y // 2
    elif direction == 1:  # pan left → center
        x = int(max_x * progress * 0.5)
        y = max_y // 2
    else:  # pure center dezoom
        x = max_x // 2
        y = max_y // 2

    x = max(0, min(x, max_x))
    y = max(0, min(y, max_y))

    cropped = img[y:y + crop_h, x:x + crop_w]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.LANCZOS))


def _build_scene_clip(scene: Scene, direction: int):
    from moviepy.editor import VideoClip

    img = _load_image(scene.image_path)
    dur = scene.duration_s

    def make_frame(t):
        return _dezoom_frame(img, t, dur, direction)

    # VideoClip (not ImageClip) accepts make_frame correctly in moviepy 1.x
    clip = VideoClip(make_frame, duration=dur)
    clip = clip.set_fps(FPS)
    return clip


def _assemble_video(scenes: list[Scene], audio_path: Path, output_path: Path) -> Path:
    from moviepy.editor import AudioFileClip, concatenate_videoclips

    clips = [_build_scene_clip(s, i % 3) for i, s in enumerate(scenes)]

    video = concatenate_videoclips(clips, method="compose") if len(clips) > 1 else clips[0]

    narration = AudioFileClip(str(audio_path))
    audio_dur = narration.duration
    video_dur = video.duration

    if audio_dur > video_dur:
        narration = narration.subclip(0, video_dur)
    else:
        video = video.subclip(0, audio_dur)

    video = video.set_audio(narration)
    video.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(output_path.parent / "temp_audio.m4a"),
        remove_temp=True,
        logger=None,
        preset="fast",
        ffmpeg_params=["-crf", "23"],
    )
    return output_path


def _mix_bgm(video_path: Path, bgm_path: Optional[Path], output_path: Path,
             subtitles: bool, srt_path: Optional[Path]) -> Path:
    if not bgm_path or not bgm_path.exists():
        if subtitles and srt_path and srt_path.exists():
            _burn_subtitles(video_path, srt_path, output_path)
            return output_path
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-c", "copy", str(output_path)],
            check=True, capture_output=True,
        )
        return output_path

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        video_dur = float(res.stdout.strip())
    except Exception:
        video_dur = 60.0

    vf = ""
    if subtitles and srt_path and srt_path.exists():
        srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf = f"subtitles='{srt_esc}':force_style='FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME},atrim=0:{video_dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264" if vf else "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd.append(str(output_path))
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> None:
    srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"subtitles='{srt_esc}':force_style='"
          "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf, "-c:a", "copy", str(output_path)],
        check=True, capture_output=True,
    )


async def render(
    scenes: list[Scene],
    audio_path: Path,
    script: ScriptOutput,
    req: GenerateRequest,
    bgm_path: Optional[Path],
    job_id: str,
) -> Path:
    loop = asyncio.get_event_loop()
    intermediate = output_video_path(job_id).parent / "intermediate.mp4"
    final = output_video_path(job_id)

    await loop.run_in_executor(None, _assemble_video, scenes, audio_path, intermediate)

    srt = subtitles_path(job_id) if req.subtitles else None
    await loop.run_in_executor(None, _mix_bgm, intermediate, bgm_path, final, req.subtitles, srt)

    if intermediate.exists() and intermediate != final:
        intermediate.unlink(missing_ok=True)

    return final
