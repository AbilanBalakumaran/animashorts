"""
Video rendering — pure FFmpeg.
Subtle alternating zoom-in / zoom-out (1.04x max) + crossfade transitions.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

from models.job import GenerateRequest
from models.scene import Scene, ScriptOutput
from storage.local import output_video_path, subtitles_path

VIDEO_W = int(os.getenv("VIDEO_WIDTH", 1080))
VIDEO_H = int(os.getenv("VIDEO_HEIGHT", 1920))
FPS = int(os.getenv("VIDEO_FPS", 24))
BGM_VOLUME = 0.12
XFADE_DUR = 0.4   # seconds crossfade between clips
ZOOM_AMOUNT = 0.04  # max zoom delta (1.0 → 1.04 or 1.04 → 1.0)


def _prepare_image(src: Optional[str], dest: Path) -> None:
    """Crop to 9:16 and resize."""
    if not src or not Path(src).exists():
        img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))
    else:
        img = Image.open(src).convert("RGB")
        sw, sh = img.size
        ratio = VIDEO_W / VIDEO_H
        if sw / sh > ratio:
            nw = int(sh * ratio)
            img = img.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
        else:
            nh = int(sw / ratio)
            img = img.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
        img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    img.save(str(dest), "JPEG", quality=92)


def _scene_to_clip(img_path: Path, duration_s: float, idx: int, out: Path) -> None:
    """
    Render one scene with subtle zoom effect.
    Even index  → slow zoom-in  (1.0 → 1.04)
    Odd index   → slow dezoom   (1.04 → 1.0)
    Slight horizontal drift alternates left/right for life.
    """
    frames = max(int(duration_s * FPS), 1)
    d = str(frames)

    zoom_in = (idx % 2 == 0)

    if zoom_in:
        z_expr = f"1+{ZOOM_AMOUNT}*(on-1)/max({d}-1,1)"
    else:
        z_expr = f"{1+ZOOM_AMOUNT}-{ZOOM_AMOUNT}*(on-1)/max({d}-1,1)"

    # Gentle horizontal drift: 2% of width over full duration
    drift = 0.02
    if idx % 3 == 0:      # drift right
        x_expr = f"iw/2-(iw/zoom/2)+(iw*{drift})*(on-1)/max({d}-1,1)"
    elif idx % 3 == 1:    # drift left
        x_expr = f"iw/2-(iw/zoom/2)-(iw*{drift})*(on-1)/max({d}-1,1)"
    else:                  # no drift, pure zoom
        x_expr = "iw/2-(iw/zoom/2)"

    y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
        f":d={d}:fps={FPS}:s={VIDEO_W}x{VIDEO_H},"
        # soft fade-in + fade-out on every clip for smooth crossfade
        f"fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(duration_s-0.3,0):.2f}:d=0.3:alpha=1"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(img_path),
            "-vf", vf,
            "-t", str(duration_s),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-an",
            str(out),
        ],
        check=True, capture_output=True,
    )


def _concat_with_xfade(clip_paths: list[Path], durations: list[float], out: Path) -> None:
    """Concatenate clips with smooth xfade crossfade transitions."""
    if len(clip_paths) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(clip_paths[0]), "-c", "copy", str(out)],
            check=True, capture_output=True,
        )
        return

    # Build xfade filter chain
    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    # Build filter_complex with chained xfade
    filter_parts = []
    offset = 0.0
    prev_label = "[0:v]"

    for i in range(1, len(clip_paths)):
        offset += durations[i - 1] - XFADE_DUR
        out_label = f"[xf{i}]" if i < len(clip_paths) - 1 else "[outv]"
        filter_parts.append(
            f"{prev_label}[{i}:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offset:.3f}{out_label}"
        )
        prev_label = f"[xf{i}]"

    filter_complex = ";".join(filter_parts)

    subprocess.run(
        [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            str(out),
        ],
        check=True, capture_output=True,
    )


def _add_audio(video_path: Path, audio_path: Path, out: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out),
        ],
        check=True, capture_output=True,
    )


def _mix_bgm(video_path: Path, bgm_path: Optional[Path], out: Path,
             subtitles: bool, srt_path: Optional[Path]) -> None:
    if not bgm_path or not bgm_path.exists():
        if subtitles and srt_path and srt_path.exists():
            _burn_subtitles(video_path, srt_path, out)
            return
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-c", "copy", str(out)],
            check=True, capture_output=True,
        )
        return

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        dur = float(res.stdout.strip())
    except Exception:
        dur = 60.0

    vf = ""
    if subtitles and srt_path and srt_path.exists():
        se = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf = (f"subtitles='{se}':force_style='"
              "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME},atrim=0:{dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264" if vf else "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd.append(str(out))
    subprocess.run(cmd, check=True, capture_output=True)


def _burn_subtitles(video_path: Path, srt_path: Path, out: Path) -> None:
    se = str(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"subtitles='{se}':force_style='"
          "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf, "-c:a", "copy", str(out)],
        check=True, capture_output=True,
    )


def _render_sync(scenes: list[Scene], audio_path: Path,
                 req: GenerateRequest, bgm_path: Optional[Path], job_id: str) -> Path:
    from storage.local import job_dir
    d = job_dir(job_id)
    clip_paths: list[Path] = []
    durations: list[float] = []

    for i, scene in enumerate(scenes):
        img_dest = d / f"prep_{i:02d}.jpg"
        _prepare_image(scene.image_path, img_dest)

        clip_out = d / f"clip_{i:02d}.mp4"
        _scene_to_clip(img_dest, scene.duration_s, i, clip_out)
        clip_paths.append(clip_out)
        durations.append(scene.duration_s)

    raw_video = d / "raw_video.mp4"
    _concat_with_xfade(clip_paths, durations, raw_video)

    with_audio = d / "with_audio.mp4"
    _add_audio(raw_video, audio_path, with_audio)

    final = output_video_path(job_id)
    srt = subtitles_path(job_id) if req.subtitles else None
    _mix_bgm(with_audio, bgm_path, final, req.subtitles, srt)

    for p in clip_paths + [raw_video, with_audio]:
        p.unlink(missing_ok=True)

    return final


async def render(scenes, audio_path, script, req, bgm_path, job_id) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _render_sync, scenes, audio_path, req, bgm_path, job_id
    )
