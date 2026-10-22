"""Chạy job trong thread nền, đẩy tiến độ qua WebSocket. Chỉ 1 job tại một thời điểm."""
from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from videodubber.models import JobRequest
from videodubber.processor import run_job

from ..state import STATE

router = APIRouter(prefix="/api/jobs")
_lock = threading.Lock()


def _worker(req: JobRequest) -> None:
    try:
        res = run_job(
            req,
            on_progress=lambda d, t, it: STATE.update_job(done=d, total=t, last=it.model_dump(mode="json")),
            should_stop=STATE.stop_flag.is_set,
        )
        status = "stopped" if STATE.stop_flag.is_set() else "done"
        STATE.update_job(status=status, ok=res.ok_count, failed=[f.model_dump(mode="json") for f in res.failed])
    except Exception as e:  # noqa: BLE001 — báo lỗi lên UI thay vì chết im lặng
        STATE.update_job(status="error", error=str(e))
    finally:
        _lock.release()


@router.post("")
def start(body: dict) -> dict:
    try:
        req = JobRequest.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False)) from e
    if not req.input_dir.is_dir():
        raise HTTPException(422, "Thư mục input không tồn tại")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "Đang có job chạy")
    STATE.stop_flag.clear()
    STATE.update_job(status="running", done=0, total=0, ok=0, failed=[], error=None, last=None)
    threading.Thread(target=_worker, args=(req,), daemon=True).start()
    return {"started": True}


@router.post("/stop")
def stop() -> dict:
    STATE.stop_flag.set()
    return {"stopping": True}


@router.get("")
def status() -> dict:
    return STATE.snapshot()["job"]
