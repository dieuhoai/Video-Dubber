"""Bản nháp phiên làm việc: giữ chữ/ngôn ngữ/bản dịch qua các lần tải lại trang, chỉ xoá khi bấm Reset."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from videodubber import store

router = APIRouter(prefix="/api/drafts")


@router.get("/{did}")
def get(did: str) -> dict:
    try:
        return store.load_draft(did) or {}
    except FileNotFoundError as e:
        raise HTTPException(404, "Mã bản nháp không hợp lệ") from e


@router.put("/{did}")
def put(did: str, body: dict = Body(...)) -> dict:  # noqa: B008 — cú pháp FastAPI
    try:
        store.save_draft(did, body)
    except FileNotFoundError as e:
        raise HTTPException(404, "Mã bản nháp không hợp lệ") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"saved": True}


@router.delete("/{did}")
def delete(did: str) -> dict:
    try:
        store.delete_draft(did)
    except FileNotFoundError as e:
        raise HTTPException(404, "Mã bản nháp không hợp lệ") from e
    return {"deleted": True}
