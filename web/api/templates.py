"""Template: upload video, sửa caption/voice/khung che, xem khung hình, tải nhạc nền."""
from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from videodubber import store
from videodubber.captions import build_ass
from videodubber.io_utils import atomic_write_text
from videodubber.langs import get_lang
from videodubber.media import MediaError, extract_frame
from videodubber.models import Template, TimedLine
from videodubber.render import preview_frame

router = APIRouter(prefix="/api/templates")
MAX_UPLOAD = 1024 * 1024 * 1024  # 1 GB


def _load(tid: str) -> Template:
    try:
        return store.load_template(tid)
    except FileNotFoundError as e:
        raise HTTPException(404, "Không tìm thấy template — có thể đã bị xoá") from e


def _save_upload(f: UploadFile, allowed: set[str], tmp: Path) -> Path:
    name = Path(f.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise HTTPException(422, f"File {ext or '(không đuôi)'} chưa hỗ trợ — dùng {', '.join(sorted(allowed))}")
    out = tmp / f"upload{ext}"
    size = 0
    with out.open("wb") as w:
        while chunk := f.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, "File lớn hơn 1 GB — hãy xuất video nhẹ hơn")
            w.write(chunk)
    return out


@router.get("")
def list_all() -> dict:
    return {"items": [t.model_dump(mode="json") for t in store.list_templates()]}


@router.post("")
def upload(video: UploadFile = File(...), name: str = Form("")) -> dict:  # noqa: B008 — cú pháp FastAPI
    with tempfile.TemporaryDirectory(prefix="vdub_up_") as tmp:
        src = _save_upload(video, store.VIDEO_EXT, Path(tmp))
        try:
            tpl = store.create_template(src, name.strip() or Path(video.filename or "Video").stem)
        except (ValueError, MediaError) as e:
            raise HTTPException(422, str(e)) from e
    return tpl.model_dump(mode="json")


@router.get("/{tid}")
def get(tid: str) -> dict:
    return _load(tid).model_dump(mode="json")


@router.put("/{tid}")
def update(tid: str, body: dict) -> dict:
    old = _load(tid)
    # Các trường do tool đo — không cho sửa từ giao diện.
    fixed = {k: getattr(old, k) for k in ("id", "video", "width", "height", "duration", "fps", "music")}
    try:
        tpl = Template.model_validate({**body, **fixed})
    except ValidationError as e:
        raise HTTPException(422, "; ".join(str(x["msg"]).removeprefix("Value error, ")
                                           for x in e.errors(include_url=False))) from e
    return store.save_template(tpl).model_dump(mode="json")


@router.delete("/{tid}")
def delete(tid: str) -> dict:
    _load(tid)
    store.delete_template(tid)
    return {"deleted": True}


@router.get("/{tid}/frame")
def frame(tid: str, t: float = 1.0) -> FileResponse:
    tpl = _load(tid)
    t = min(max(t, 0.0), max(tpl.duration - 0.05, 0.0))
    cache = store.template_dir(tid) / "frames"
    cache.mkdir(exist_ok=True)
    out = cache / f"{round(t * 10):05d}.jpg"
    if not out.is_file():
        try:
            extract_frame(store.template_dir(tid) / tpl.video, t, out)
        except MediaError as e:
            raise HTTPException(500, str(e)) from e
    return FileResponse(out, media_type="image/jpeg")


@router.get("/{tid}/video")
def video(tid: str) -> FileResponse:
    tpl = _load(tid)
    return FileResponse(store.template_dir(tid) / tpl.video, media_type="video/mp4")


@router.post("/{tid}/music")
def music(tid: str, file: UploadFile = File(...)) -> dict:  # noqa: B008
    _load(tid)
    with tempfile.TemporaryDirectory(prefix="vdub_up_") as tmp:
        src = _save_upload(file, store.AUDIO_EXT, Path(tmp))
        try:
            tpl = store.set_music(tid, src)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return tpl.model_dump(mode="json")



@router.post("/{tid}/preview")
def preview(tid: str, body: dict, tasks: BackgroundTasks) -> FileResponse:
    """Xem trước caption mới trên 1 khung hình, dùng kiểu chữ/khung che đang chỉnh (chưa cần lưu)."""
    old = _load(tid)
    fixed = {k: getattr(old, k) for k in ("id", "video", "width", "height", "duration", "fps", "music")}
    try:
        tpl = Template.model_validate({**(body.get("template") or old.model_dump()), **fixed})
        lang = get_lang(str(body.get("lang") or "fr"))
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, "Thông số chưa hợp lệ — kiểm tra lại các ô đang nhập") from e
    text = str(body.get("text") or (tpl.captions[0].text if tpl.captions else "Caption"))[:500]
    t = min(max(float(body.get("t") or 1.0), 0.0), max(tpl.duration - 0.05, 0.0))
    with tempfile.TemporaryDirectory(prefix="vdub_pv_") as tmp:
        ass_text, _ = build_ass([TimedLine(start=0, end=60, text=text)], [text], tpl.style, tpl.width, tpl.height,
                                lang.spaces)
        ass = Path(tmp) / "p.ass"
        atomic_write_text(ass, ass_text)
        cache = store.template_dir(tid) / "frames"
        cache.mkdir(exist_ok=True)
        out = cache / f"preview_{secrets.token_hex(4)}.jpg"  # mỗi người xem 1 file, xoá sau khi gửi
        tasks.add_task(out.unlink, missing_ok=True)
        try:
            preview_frame(store.template_dir(tid) / tpl.video, t, ass, tpl.cover, out, Path(tmp),
                          size=(tpl.width, tpl.height))
        except MediaError as e:
            raise HTTPException(500, str(e)) from e
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
