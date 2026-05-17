"""
Video rendering — pure FFmpeg.
Alternating subtle zoom-in / dezoom (1.04x) + xfade crossfade transitions.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image

from models.job import GenerateRequest
from models.scene import Scene, ScriptOutput
from storage.local import output_video_path, subtitles_path

VIDEO_W   = int(os.getenv("VIDEO_WIDTH",  1080))
VIDEO_H   = int(os.getenv("VIDEO_HEIGHT", 1920))
FPS       = int(os.getenv("VIDEO_FPS",    24))
BGM_VOL   = 0.12
XFADE_DUR = 0.4    # crossfade duration in seconds
ZOOM_AMT  = 0.04   # max zoom delta — subtle (1.0 ↔ 1.04)

# Padded dimensions for Ken Burns headroom (must be even for H.264)
_PAD_W = VIDEO_W + int(VIDEO_W * ZOOM_AMT)
_PAD_W += _PAD_W % 2
_PAD_H = VIDEO_H + int(VIDEO_H * ZOOM_AMT)
_PAD_H += _PAD_H % 2
_DW = _PAD_W - VIDEO_W   # pixel headroom width  (≈44)
_DH = _PAD_H - VIDEO_H   # pixel headroom height (≈76)


def _ffmpeg(args: list[str], label: str = "") -> None:
    """Run FFmpeg, raise with readable stderr on failure."""
    result = subprocess.run(["ffmpeg"] + args, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed{f' ({label})' if label else ''}: "
            f"{result.stderr.decode(errors='replace')[-800:]}"
        )


def _prepare_image(src: Optional[str], dest: Path) -> None:
    """Crop to 9:16 and resize to target resolution."""
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


def _scene_to_clip(img: Path, dur: float, idx: int, out: Path) -> None:
    """
    Ken Burns pan — scale to padded size (constant 1.04x zoom baked in),
    then animate a fixed VIDEO_W x VIDEO_H crop window with x driven by `n`.

    Fixed crop w/h = output dimensions never change = no filter-graph reinit.
    Even scenes pan left→right, odd scenes pan right→left.
    """
    frames = max(int(dur * FPS), 2)
    step   = round(_DW / max(frames - 1, 1), 4)   # px per frame

    if idx % 2 == 0:
        x_expr = f"n*{step}"           # 0 → _DW
    else:
        x_expr = f"{_DW}-n*{step}"     # _DW → 0

    vf = (
        f"scale={_PAD_W}:{_PAD_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H}:x={x_expr}:y={_DH // 2}"
    )

    _ffmpeg([
        "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(img),
        "-vf", vf,
        "-vframes", str(frames),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an",
        "-threads", "0",
        str(out),
    ], f"scene {idx}")


def _concat_xfade(clips: list[Path], durations: list[float], out: Path) -> None:
    """Concatenate clips with smooth xfade crossfade."""
    if len(clips) == 1:
        _ffmpeg(["-y", "-i", str(clips[0]), "-c", "copy", str(out)], "concat-single")
        return

    inputs = []
    for p in clips:
        inputs += ["-i", str(p)]

    parts = []
    offset = 0.0
    prev = "[0:v]"

    for i in range(1, len(clips)):
        offset += durations[i - 1] - XFADE_DUR
        label = f"[xf{i}]" if i < len(clips) - 1 else "[outv]"
        parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offset:.3f}{label}"
        )
        prev = f"[xf{i}]"

    _ffmpeg([
        "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(out),
    ], "xfade-concat")


def _add_audio(video: Path, audio: Path, out: Path) -> None:
    _ffmpeg([
        "-y", "-i", str(video), "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ], "add-audio")


def _mix_bgm(video: Path, bgm: Optional[Path], out: Path,
             subtitles: bool, srt: Optional[Path]) -> None:
    if not bgm or not bgm.exists():
        if subtitles and srt and srt.exists():
            _burn_subs(video, srt, out)
            return
        _ffmpeg(["-y", "-i", str(video), "-c", "copy", str(out)], "copy-no-bgm")
        return

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    try:
        dur = float(result.stdout.strip())
    except Exception:
        dur = 60.0

    vf = ""
    if subtitles and srt and srt.exists():
        se = str(srt).replace("\\", "/").replace(":", "\\:")
        vf = (f"subtitles='{se}':force_style='"
              "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")

    cmd = [
        "-y", "-i", str(video),
        "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex",
        f"[1:a]volume={BGM_VOL},atrim=0:{dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264" if vf else "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd.append(str(out))
    _ffmpeg(cmd, "mix-bgm")


def _burn_subs(video: Path, srt: Path, out: Path) -> None:
    se = str(srt).replace("\\", "/").replace(":", "\\:")
    vf = (f"subtitles='{se}':force_style='"
          "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")
    _ffmpeg(["-y", "-i", str(video), "-vf", vf, "-c:a", "copy", str(out)], "burn-subs")


def _render_sync(scenes: list[Scene], audio: Path,
                 req: GenerateRequest, bgm: Optional[Path], job_id: str) -> Path:
    from storage.local import job_dir
    d = job_dir(job_id)
    clips: list[Path] = []
    durations: list[float] = []

    for i, scene in enumerate(scenes):
        img = d / f"prep_{i:02d}.jpg"
        _prepare_image(scene.image_path, img)
        clip = d / f"clip_{i:02d}.mp4"
        _scene_to_clip(img, scene.duration_s, i, clip)
        clips.append(clip)
        durations.append(scene.duration_s)

    raw   = d / "raw_video.mp4"
    mixed = d / "with_audio.mp4"
    final = output_video_path(job_id)

    _concat_xfade(clips, durations, raw)
    _add_audio(raw, audio, mixed)

    srt_path = subtitles_path(job_id) if req.subtitles else None
    _mix_bgm(mixed, bgm, final, req.subtitles, srt_path)

    for p in clips + [raw, mixed]:
        p.unlink(missing_ok=True)

    return final


async def render(scenes, audio_path, script, req, bgm_path, job_id) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _render_sync, scenes, audio_path, req, bgm_path, job_id
    )
