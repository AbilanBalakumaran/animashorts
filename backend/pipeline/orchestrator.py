"""
Main pipeline orchestrator — runs as a Celery task.
Coordinates all stages: script → TTS → images → render.
Writes job status to Redis at each stage boundary.
"""

import json
import os
import traceback
from pathlib import Path

from workers.celery_app import celery_app
from models.job import JobStatus, JobStep, GenerateRequest
from models import ScriptOutput
from api.deps import get_redis
from storage.local import output_url

import pipeline.script_gen as script_gen
import pipeline.tts as tts
import pipeline.image_gen as image_gen
import pipeline.music as music
import pipeline.subtitle as subtitle
import pipeline.video_editor as video_editor


def _save_status(status: JobStatus) -> None:
    r = get_redis()
    r.set(f"job:{status.job_id}", status.model_dump_json(), ex=86400)


def _load_status(job_id: str) -> JobStatus | None:
    r = get_redis()
    raw = r.get(f"job:{job_id}")
    if raw:
        return JobStatus.model_validate_json(raw)
    return None


@celery_app.task(bind=True, name="pipeline.orchestrator.run_pipeline")
def run_pipeline(self, job_id: str, payload: dict) -> None:
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_pipeline(job_id, payload))
    finally:
        loop.close()


async def _async_pipeline(job_id: str, payload: dict) -> None:
    req = GenerateRequest(**payload)
    status = JobStatus(job_id=job_id)

    try:
        # ── Stage 1: Script generation ─────────────────────────────────────
        status.advance(JobStep.script)
        _save_status(status)

        script: ScriptOutput = await script_gen.generate(req)

        # ── Stage 2: Text-to-speech ────────────────────────────────────────
        status.advance(JobStep.tts)
        _save_status(status)

        audio_path = await tts.synthesize(script.narration, job_id)

        # Extract timestamps for subtitles
        word_timestamps = []
        if req.subtitles:
            word_timestamps = await tts.get_word_timestamps(audio_path)
            if word_timestamps:
                subtitle.generate_srt(word_timestamps, job_id)

        # ── Stage 3: Image generation ──────────────────────────────────────
        status.advance(JobStep.images)
        _save_status(status)

        scenes = await image_gen.generate_scenes(script.scenes, job_id)
        script.scenes = scenes  # update with image paths

        # ── Music selection (parallel with image gen is fine too) ──────────
        bgm_path, _ = await music.get_music_for_script(script.narration, script.mood)

        # ── Stage 4: Video render ──────────────────────────────────────────
        status.advance(JobStep.render)
        _save_status(status)

        final_path = await video_editor.render(
            scenes=script.scenes,
            audio_path=audio_path,
            script=script,
            req=req,
            bgm_path=bgm_path,
            job_id=job_id,
        )

        # ── Done ───────────────────────────────────────────────────────────
        status.advance(JobStep.done)
        status.output_url = output_url(job_id)
        _save_status(status)

    except Exception as exc:
        status.advance(JobStep.error, error=str(exc))
        _save_status(status)
        raise
