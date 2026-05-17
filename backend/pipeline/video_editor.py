"""
Video rendering — pure FFmpeg pipeline (no MoviePy frame loop).
FFmpeg zoompan filter handles dezoom natively in C → 10x faster than MoviePy+PIL.
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


def _prepare_image(src: Optional[str], dest: Path) -> None:
    """Crop + resize image to 9:16, save as JPEG for FFmpeg."""
    if not src or not Path(src).exists():
        img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))
    else:
        img = Image.open(src).convert("RGB")
        sw, sh = img.size
        target = VIDEO_W / VIDEO_H
        if sw / sh > target:
            nw = int(sh * target)
            img = img.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
        else:
            nh = int(sw / target)
            img = img.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
        img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    img.save(str(dest), "JPEG", quality=92)


def _scene_to_clip(img_path: Path, duration_s: float, direction: int, out: Path) -> None:
    """Render one scene with FFmpeg zoompan dezoom."""
    frames = max(int(duration_s * FPS), 1)
    d_expr = str(frames)

    # Dezoom: z goes from 1.15 down to 1.0
    z_expr = f"1.15-0.15*(on-1)/max({d_expr}-1,1)"

    if direction == 0:      # pan from slightly right → center while dezooming
        x_expr = f"iw/2-(iw/zoom/2)+(iw*0.05)*(1-(on-1)/max({d_expr}-1,1))"
    elif direction == 1:    # pan from slightly left → center
        x_expr = f"iw/2-(iw/zoom/2)-(iw*0.05)*(1-(on-1)/max({d_expr}-1,1))"
    else:                   # pure center dezoom
        x_expr = "iw/2-(iw/zoom/2)"

    y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
        f":d={d_expr}:fps={FPS}:s={VIDEO_W}x{VIDEO_H}"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(img_path),
            "-vf", vf,
            "-t", str(duration_s),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def _concat_clips(clip_paths: list[Path], out: Path) -> None:
    """Concatenate clips with FFmpeg concat demuxer (stream copy = instant)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in clip_paths:
            f.write(f"file '{p.as_posix()}'\n")
        list_file = f.name

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    Path(list_file).unlink(missing_ok=True)


def _add_audio(video_path: Path, audio_path: Path, out: Path) -> None:
    """Mux video + narration, trim to shorter of the two."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out),
        ],
        check=True,
        capture_output=True,
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
        srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf = (f"subtitles='{srt_esc}':force_style='"
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
    srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"subtitles='{srt_esc}':force_style='"
          "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vf", vf, "-c:a", "copy", str(out)],
        check=True, capture_output=True,
    )


def _render_sync(scenes: list[Scene], audio_path: Path,
                 req: GenerateRequest, bgm_path: Optional[Path],
                 job_id: str) -> Path:
    from storage.local import job_dir

    d = job_dir(job_id)
    clip_paths: list[Path] = []

    for i, scene in enumerate(scenes):
        img_dest = d / f"prep_{i:02d}.jpg"
        _prepare_image(scene.image_path, img_dest)

        clip_out = d / f"clip_{i:02d}.mp4"
        _scene_to_clip(img_dest, scene.duration_s, i % 3, clip_out)
        clip_paths.append(clip_out)

    raw_video = d / "raw_video.mp4"
    _concat_clips(clip_paths, raw_video)

    with_audio = d / "with_audio.mp4"
    _add_audio(raw_video, audio_path, with_audio)

    final = output_video_path(job_id)
    srt = subtitles_path(job_id) if req.subtitles else None
    _mix_bgm(with_audio, bgm_path, final, req.subtitles, srt)

    # Cleanup intermediates
    for p in clip_paths + [raw_video, with_audio]:
        p.unlink(missing_ok=True)

    return final


async def render(
    scenes: list[Scene],
    audio_path: Path,
    script: ScriptOutput,
    req: GenerateRequest,
    bgm_path: Optional[Path],
    job_id: str,
) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _render_sync, scenes, audio_path, req, bgm_path, job_id
    )
