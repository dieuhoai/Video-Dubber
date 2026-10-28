"""Chạy batch trong thread nền, đẩy tiến độ qua WebSocket. Một batch tại một thời điểm (máy chủ render tuần tự)."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from videodubber import store
from videodubber.media import MediaError
from videodubber.models import BatchRequest
from videodubber.processor import run_batch, validate_variant

from ..state import STATE

router = APIRouter(prefix="/api/jobs")
_lock = threading.Lock()


def _worker(req: BatchRequest, batch: tuple[str, object]) -> None:
    items: list[dict] = []

    def progress(done: int, total: int, it) -> None:
        items.append(it.model_dump(mode="json"))
        STATE.update_job(done=done, total=total, items=list(items))

    try:
        res = run_batch(req, on_progress=progress, should_stop=STATE.stop_flag.is_set, batch=batch,
                        on_stage=lambda text: STATE.update_job(stage=text))
        status = "stopped" if STATE.stop_flag.is_set() else "done"
        STATE.update_job(status=status, ok=res.ok_count, failed=[f.model_dump(mode="json") for f in res.failed])
    except Exception as e:  # noqa: BLE001 — báo lỗi lên UI thay vì chết im lặng
        logging.getLogger("videodubber").exception("Batch lỗi")
        STATE.update_job(status="error", error=str(e))
    finally:
        _lock.release()


@router.post("")
def start(body: dict) -> dict:
    try:
        req = BatchRequest.model_validate(body)
        tpls = [store.load_template(tid) for tid in req.all_template_ids]
        tpl = tpls[0]
        for t in tpls:
            for v in req.variants:
                try:
                    validate_variant(t, v)
                except ValueError as e:
                    raise ValueError(f"Video “{t.name}”: {e}" if len(tpls) > 1 else str(e)) from e
    except ValidationError as e:
        raise HTTPException(422, "; ".join(str(x["msg"]).removeprefix("Value error, ")
                                           for x in e.errors(include_url=False))) from e
    except FileNotFoundError as e:
        raise HTTPException(404, "Không tìm thấy template") from e
    except (ValueError, MediaError) as e:
        raise HTTPException(422, str(e)) from e
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "Máy chủ đang render một batch khác — đợi xong rồi bấm lại")
    batch = store.new_batch(tpl)
    STATE.stop_flag.clear()
    STATE.update_job(status="running", batch_id=batch[0], template_id=tpl.id, done=0,
                     total=len(req.variants) * len(tpls),
                     items=[], ok=0, failed=[], error=None, stage="Bắt đầu…")
    threading.Thread(target=_worker, args=(req, batch), daemon=True).start()
    return {"started": True, "batch_id": batch[0]}


@router.post("/stop")
def stop() -> dict:
    STATE.stop_flag.set()
    return {"stopping": True}


@router.get("")
def status() -> dict:
    return STATE.snapshot()["job"]
