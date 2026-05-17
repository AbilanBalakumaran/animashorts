"""
Video rendering pipeline stage.
Uses MoviePy for clip assembly (Ken Burns effects, crossfades) and
FFmpeg for final export with audio mixing and optional subtitle burn-in.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from models.job import GenerateRequest
from models.scene import Scene, ScriptOutput
from storage.local import output_video_path, subtitles_path

VIDEO_W = int(os.getenv("VIDEO_WIDTH", 1080))
VIDEO_H = int(os.getenv("VIDEO_HEIGHT", 1920))
FPS = int(os.getenv("VIDEO_FPS", 30))
TRANSITION_DURATION = 0.3
BGM_VOLUME = 0.12
NARRATION_VOLUME = 1.0


def _ken_burns_frame(img_array: np.ndarray, t: float, duration: float, direction: int) -> np.ndarray:
    """Apply Ken Burns zoom+pan effect to a single frame."""
    h, w = img_array.shape[:2]
    progress = t / max(duration, 0.001)

    zoom = 1.0 + 0.15 * progress
    crop_w = int(w / zoom)
    crop_h = int(h / zoom)

    if direction == 0:  # zoom in from left
        x = int((w - crop_w) * progress * 0.5)
        y = int((h - crop_h) * 0.5)
    elif direction == 1:  # zoom in from right
        x = int((w - crop_w) * (1 - progress * 0.5))
        y = int((h - crop_h) * 0.5)
    else:  # center zoom
        x = int((w - crop_w) * 0.5)
        y = int((h - crop_h) * 0.5)

    cropped = img_array[y:y + crop_h, x:x + crop_w]
    img_pil = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
    return np.array(img_pil)


def _build_scene_clip(scene: Scene, direction: int):
    from moviepy.editor import ImageClip

    if not scene.image_path or not Path(scene.image_path).exists():
        img_array = np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
    else:
        img = Image.open(scene.image_path).convert("RGB")
        img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
        img_array = np.array(img)

    def make_frame(t):
        return _ken_burns_frame(img_array, t, scene.duration_s, direction)

    clip = ImageClip(make_frame=make_frame, duration=scene.duration_s)
    clip = clip.set_fps(FPS)
    return clip


def _assemble_video_moviepy(
    scenes: list[Scene],
    audio_path: Path,
    output_path: Path,
) -> Path:
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        concatenate_videoclips,
    )

    clips = [_build_scene_clip(s, i % 3) for i, s in enumerate(scenes)]

    if len(clips) > 1:
        from moviepy.editor import concatenate_videoclips
        video = concatenate_videoclips(clips, method="compose", padding=-TRANSITION_DURATION)
    else:
        video = clips[0]

    narration = AudioFileClip(str(audio_path)).volumex(NARRATION_VOLUME)

    video_duration = video.duration
    audio_duration = narration.duration
    if audio_duration > video_duration:
        narration = narration.subclip(0, video_duration)
    else:
        video = video.subclip(0, audio_duration)

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


def _mix_bgm_ffmpeg(
    video_path: Path,
    bgm_path: Optional[Path],
    output_path: Path,
    subtitles: bool,
    srt_path: Optional[Path],
) -> Path:
    """Use FFmpeg to mix BGM at low volume and optionally burn subtitles."""
    if not bgm_path or not bgm_path.exists():
        if subtitles and srt_path and srt_path.exists():
            _burn_subtitles(video_path, srt_path, output_path)
            return output_path
        # No BGM, no subtitles — just copy
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-c", "copy", str(output_path)],
            check=True,
            capture_output=True,
        )
        return output_path

    # Prepare subtitle filter
    vf_filter = ""
    if subtitles and srt_path and srt_path.exists():
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf_filter = f"subtitles='{srt_escaped}':force_style='FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'"

    video_duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
    ]
    result = subprocess.run(video_duration_cmd, capture_output=True, text=True)
    try:
        video_dur = float(result.stdout.strip())
    except Exception:
        video_dur = 60.0

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME},atrim=0:{video_dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "libx264" if vf_filter else "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
    ]

    if vf_filter:
        cmd += ["-vf", vf_filter]

    cmd.append(str(output_path))

    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> Path:
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = (
        f"subtitles='{srt_escaped}':force_style='"
        "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf, "-c:a", "copy", str(output_path)],
        check=True,
        capture_output=True,
    )
    return output_path


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

    await loop.run_in_executor(
        None,
        _assemble_video_moviepy,
        scenes,
        audio_path,
        intermediate,
    )

    srt_path = subtitles_path(job_id) if req.subtitles else None

    await loop.run_in_executor(
        None,
        _mix_bgm_ffmpeg,
        intermediate,
        bgm_path,
        final,
        req.subtitles,
        srt_path,
    )

    if intermediate.exists() and intermediate != final:
        intermediate.unlink(missing_ok=True)

    return final
