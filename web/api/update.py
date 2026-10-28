"""Tự cập nhật: kiểm tra bản mới, tải + cài, tự khởi động lại (tab trình duyệt tự tải lại khi xong)."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException

from videodubber import __version__, updater

from ..state import STATE

router = APIRouter(prefix="/api")
_up: dict = {"running": False, "stage": "", "done": 0, "total": 0, "error": None, "target": None}
_lock = threading.Lock()


@router.get("/version")
def version() -> dict:
    return {"version": __version__}


@router.get("/update")
def check(force: bool = False) -> dict:
    return {**updater.status(force), "progress": dict(_up)}


def _run(rel: updater.Release, args: list[str]) -> None:
    try:
        updater.perform(rel, args, lambda stage, done, total: _up.update(stage=stage, done=done, total=total))
    except Exception as e:  # noqa: BLE001 — lỗi gì cũng báo lên giao diện, tool vẫn chạy bản cũ
        logging.getLogger("videodubber").exception("Cập nhật lỗi")
        _up.update(error=str(e) if isinstance(e, (updater.UpdateError, RuntimeError)) else f"Cập nhật lỗi: {e}")
    finally:
        _up.update(running=False)
        _lock.release()


@router.post("/update")
def start() -> dict:
    if STATE.job.get("status") == "running":
        raise HTTPException(409, "Đang xuất video — đợi xong (hoặc bấm Dừng) rồi hãy cập nhật.")
    st = updater.status(force=True)
    if not st.get("available"):
        raise HTTPException(409, st.get("error") or "Bạn đang dùng bản mới nhất.")
    if st.get("blocked"):
        raise HTTPException(409, st["blocked"])
    if not _lock.acquire(blocking=False):
        return {"started": False, "running": True}
    rel = updater.Release(**st["latest"])
    _up.update(running=True, stage="download", done=0, total=0, error=None, target=rel.version)
    args = updater.relaunch_args(STATE.argv, STATE.port, STATE.token)
    threading.Thread(target=_run, args=(rel, args), daemon=True).start()
    return {"started": True, "target": rel.version}
