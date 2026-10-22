"""Kết quả các batch: danh sách, phát/tải từng video, tải ZIP."""
from __future__ import annotations

import re
import secrets
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from videodubber import store

router = APIRouter(prefix="/api/batches")
SAFE = re.compile(r"^[A-Za-z0-9._-]{1,200}\.mp4$")


def _dir(bid: str) -> Path:
    try:
        d = store.batch_dir(bid)
    except FileNotFoundError as e:
        raise HTTPException(404, "Không tìm thấy batch") from e
    if not d.is_dir():
        raise HTTPException(404, "Không tìm thấy batch")
    return d


@router.get("")
def list_all() -> dict:
    return {"items": store.list_batches()}


@router.get("/{bid}/files/{name}")
def file(bid: str, name: str, download: bool = False) -> FileResponse:
    if not SAFE.match(name):
        raise HTTPException(404, "Tên file không hợp lệ")
    p = _dir(bid) / name
    if not p.is_file():
        raise HTTPException(404, "Không thấy video — có thể batch đã bị xoá")
    return FileResponse(p, media_type="video/mp4", filename=name if download else None)


@router.get("/{bid}/zip")
def zip_all(bid: str, tasks: BackgroundTasks) -> FileResponse:
    d = _dir(bid)
    vids = sorted(d.glob("*.mp4"))
    if not vids:
        raise HTTPException(404, "Batch chưa có video nào")
    out = d / f".{secrets.token_hex(6)}.zip.tmp"  # tên riêng mỗi lần: 2 người tải cùng lúc không đè nhau
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:  # MP4 đã nén, nén thêm chỉ tốn CPU
        for v in vids:
            z.write(v, v.name)
    tasks.add_task(out.unlink, missing_ok=True)
    return FileResponse(out, media_type="application/zip", filename=f"videodubber_{bid}.zip")
