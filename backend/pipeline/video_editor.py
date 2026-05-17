"""
Video rendering — PIL-driven Ken Burns + FFmpeg mux.
Each scene is rendered frame-by-frame in Python (zoom-in / dezoom alternating),
piped as rawvideo to FFmpeg for H.264 encoding.
No dynamic FFmpeg filter expressions → no zoompan / crop reinit issues.
Clips are concatenated with hard cuts (no crossfade).
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

VIDEO_W  = int(os.getenv("VIDEO_WIDTH",  1080))
VIDEO_H  = int(os.getenv("VIDEO_HEIGHT", 1920))
FPS      = int(os.getenv("VIDEO_FPS",    24))
BGM_VOL  = 0.12
ZOOM_AMT = 0.05   # 5% zoom range — visually clear but still subtle


def _ffmpeg(args: list[str], label: str = "") -> None:
    result = subprocess.run(["ffmpeg"] + args, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed{f' ({label})' if label else ''}: "
            f"{result.stderr.decode(errors='replace')[-800:]}"
        )


def _prepare_image(src: Optional[str], dest: Path) -> None:
    """Crop to 9:16, resize to VIDEO_W × VIDEO_H."""
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


def _scene_to_clip(img_path: Path, dur: float, idx: int, out: Path) -> None:
    """
    Ken Burns: zoompan with 4 alternating patterns (zoom + pan direction).
    Single input frame + d=N → zoompan emits exactly N frames, no -loop.
    No s= / fps= params, no commas in expressions — safe on any FFmpeg build.

    x formula (iw-iw/zoom)*progress is self-clamping: at zoom=1.0 it equals
    0, so x is always within valid bounds regardless of zoom level.

    Falls back to static clip if zoompan fails.
    """
    frames = max(int(dur * FPS), 2)
    fm1    = max(frames - 1, 1)
    rate   = round(ZOOM_AMT / fm1, 8)
    zm     = round(1.0 + ZOOM_AMT, 4)

    pattern = idx % 4
    if pattern == 0:
        # zoom-in + pan left→right
        z_expr = f"1.0+on*{rate}"
        x_expr = f"(iw-iw/zoom)*on/{fm1}"
        y_expr = "ih/2-ih/zoom/2"
    elif pattern == 1:
        # dezoom + pan right→left
        z_expr = f"{zm}-on*{rate}"
        x_expr = f"(iw-iw/zoom)*({fm1}-on)/{fm1}"
        y_expr = "ih/2-ih/zoom/2"
    elif pattern == 2:
        # zoom-in + pan right→left
        z_expr = f"1.0+on*{rate}"
        x_expr = f"(iw-iw/zoom)*({fm1}-on)/{fm1}"
        y_expr = "ih/4"
    else:
        # dezoom + pan left→right
        z_expr = f"{zm}-on*{rate}"
        x_expr = f"(iw-iw/zoom)*on/{fm1}"
        y_expr = "ih/4"

    vf_zoom = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},"
        f"zoompan=z={z_expr}:x={x_expr}:y={y_expr}:d={frames}"
    )
    vf_static = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H}"
    )

    base_args = [
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-profile:v", "main", "-level", "4.0",
        "-pix_fmt", "yuv420p", "-an", "-threads", "0", str(out),
    ]

    try:
        _ffmpeg([
            "-y", "-framerate", str(FPS), "-i", str(img_path),
            "-vf", vf_zoom, "-vframes", str(frames),
            *base_args,
        ], f"scene {idx} zoom")
    except RuntimeError:
        _ffmpeg([
            "-y", "-loop", "1", "-t", f"{dur + 0.2}",
            "-framerate", str(FPS), "-i", str(img_path),
            "-vf", vf_static, "-vframes", str(frames),
            *base_args,
        ], f"scene {idx} static")


def _concat_clips(clips: list[Path], out: Path) -> None:
    """Hard-cut concatenation — no transitions."""
    if len(clips) == 1:
        _ffmpeg(["-y", "-i", str(clips[0]), "-c", "copy", str(out)], "concat-single")
        return

    list_file = out.parent / "concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in clips),
        encoding="utf-8",
    )
    _ffmpeg([
        "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out),
    ], "concat")
    list_file.unlink(missing_ok=True)


def _add_audio(video: Path, audio: Path, out: Path) -> None:
    _ffmpeg([
        "-y", "-i", str(video), "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out),
    ], "add-audio")


def _mix_bgm(video: Path, bgm: Optional[Path], out: Path,
             subtitles: bool, srt: Optional[Path]) -> None:
    if not bgm or not bgm.exists():
        if subtitles and srt and srt.exists():
            _burn_subs(video, srt, out)
            return
        _ffmpeg([
            "-y", "-i", str(video), "-c", "copy",
            "-movflags", "+faststart", str(out),
        ], "copy-no-bgm")
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
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart",
    ]
    if vf:
        cmd += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
            "-vf", vf,
        ]
    else:
        cmd += ["-c:v", "copy"]
    cmd.append(str(out))
    _ffmpeg(cmd, "mix-bgm")


def _burn_subs(video: Path, srt: Path, out: Path) -> None:
    se = str(srt).replace("\\", "/").replace(":", "\\:")
    vf = (f"subtitles='{se}':force_style='"
          "FontSize=48,FontName=Arial,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'")
    _ffmpeg([
        "-y", "-i", str(video), "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(out),
    ], "burn-subs")


def _check(path: Path, label: str) -> None:
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"Pipeline step produced empty/missing file: {label} ({path})")


def _render_sync(scenes: list[Scene], audio: Path,
                 req: GenerateRequest, bgm: Optional[Path], job_id: str) -> Path:
    from storage.local import job_dir
    d = job_dir(job_id)
    clips: list[Path] = []

    for i, scene in enumerate(scenes):
        img = d / f"prep_{i:02d}.jpg"
        _prepare_image(scene.image_path, img)
        clip = d / f"clip_{i:02d}.mp4"
        _scene_to_clip(img, scene.duration_s, i, clip)
        _check(clip, f"clip {i}")
        clips.append(clip)

    raw   = d / "raw_video.mp4"
    mixed = d / "with_audio.mp4"
    final = output_video_path(job_id)

    _concat_clips(clips, raw)
    _check(raw, "concat")
    _add_audio(raw, audio, mixed)
    _check(mixed, "add-audio")

    srt_path = subtitles_path(job_id) if req.subtitles else None
    _mix_bgm(mixed, bgm, final, req.subtitles, srt_path)
    _check(final, "final video")

    for p in clips + [raw, mixed]:
        p.unlink(missing_ok=True)

    return final


async def render(scenes, audio_path, script, req, bgm_path, job_id) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _render_sync, scenes, audio_path, req, bgm_path, job_id
    )
