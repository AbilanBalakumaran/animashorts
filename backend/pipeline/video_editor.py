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
    Render one scene with progressive Ken Burns zoom via PIL frame loop.
    Even scenes  → zoom-in  (camera moves closer over the clip)
    Odd  scenes  → dezoom   (camera pulls back over the clip)

    Strategy: upscale the image to (1+ZOOM_AMT)× so we always have extra
    pixels, then animate the crop window from wide→tight or tight→wide,
    downscaling each crop to VIDEO_W×VIDEO_H. Pure downscale = sharp frames.
    """
    frames = max(int(dur * FPS), 2)

    # Source image at padded size (always downsample → sharp)
    pad_w = VIDEO_W + int(VIDEO_W * ZOOM_AMT * 2)
    pad_h = VIDEO_H + int(VIDEO_H * ZOOM_AMT * 2)
    pad_w += pad_w % 2
    pad_h += pad_h % 2

    src = Image.open(str(img_path)).convert("RGB").resize(
        (pad_w, pad_h), Image.LANCZOS
    )

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{VIDEO_W}x{VIDEO_H}",
            "-pix_fmt", "rgb24",
            "-r", str(FPS),
            "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an",
            "-threads", "0",
            str(out),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        for n in range(frames):
            t = n / max(frames - 1, 1)   # 0.0 → 1.0

            if idx % 2 == 0:
                cw = int(pad_w - (pad_w - VIDEO_W) * t)
                ch = int(pad_h - (pad_h - VIDEO_H) * t)
            else:
                cw = int(VIDEO_W + (pad_w - VIDEO_W) * t)
                ch = int(VIDEO_H + (pad_h - VIDEO_H) * t)

            x = (pad_w - cw) // 2
            y = (pad_h - ch) // 2

            frame = src.crop((x, y, x + cw, y + ch)).resize(
                (VIDEO_W, VIDEO_H), Image.BILINEAR
            )
            try:
                proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError):
                break  # FFmpeg closed stdin (likely an error) — stop feeding

    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed (scene {idx}): {stderr.decode(errors='replace')[-800:]}"
        )


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

    for i, scene in enumerate(scenes):
        img = d / f"prep_{i:02d}.jpg"
        _prepare_image(scene.image_path, img)
        clip = d / f"clip_{i:02d}.mp4"
        _scene_to_clip(img, scene.duration_s, i, clip)
        clips.append(clip)

    raw   = d / "raw_video.mp4"
    mixed = d / "with_audio.mp4"
    final = output_video_path(job_id)

    _concat_clips(clips, raw)
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
