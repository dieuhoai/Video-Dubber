"""Lưu template và batch trên đĩa: DATA_DIR/templates/<id>/, DATA_DIR/batches/<id>/."""
from __future__ import annotations

import json
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

from . import defaults as D
from .io_utils import read_json, write_json
from .media import probe
from .models import Box, CaptionStyle, JobResult, Template, TimedLine

ID = re.compile(r"^[a-z0-9]{6,32}$")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def _check_id(i: str) -> str:
    if not ID.match(i):
        raise FileNotFoundError("Mã không hợp lệ")
    return i


def template_dir(tid: str) -> Path:
    return D.DATA_DIR / "templates" / _check_id(tid)


def batch_dir(bid: str) -> Path:
    return D.DATA_DIR / "batches" / _check_id(bid)


def new_id() -> str:
    return secrets.token_hex(6)


def default_style(width: int, height: int) -> tuple[CaptionStyle, Box]:
    """Vị trí hay gặp của caption hook trên video dọc: ~2/3 chiều cao, gần full ngang."""
    k = width / 720
    style = CaptionStyle(size=round(54 * k), center_x=width // 2, center_y=round(height * 0.72),
                         max_width=round(width * 0.94), outline=round(3 * k, 1))
    box_h = round(height * 0.2)
    return style, Box(x=0, y=min(style.center_y - box_h // 2, height - box_h), w=width, h=box_h)


def create_template(video_src: Path, name: str) -> Template:
    """Chép video vào kho và tạo template rỗng (người dùng điền caption/voice sau)."""
    ext = video_src.suffix.lower()
    if ext not in VIDEO_EXT:
        raise ValueError(f"Định dạng {ext or '(không có)'} chưa hỗ trợ — dùng MP4/MOV.")
    info = probe(video_src)
    tid = new_id()
    d = template_dir(tid)
    d.mkdir(parents=True)
    shutil.copy2(video_src, d / f"source{ext}")
    style, box = default_style(info.width, info.height)
    tpl = Template(id=tid, name=name[:120] or "Video", video=f"source{ext}", width=info.width, height=info.height,
                   duration=round(info.duration, 3), fps=round(info.fps, 3), style=style, cover=box,
                   audio_mode="original")
    save_template(tpl)
    return tpl


def _scaled_lines(lines: list[TimedLine], duration: float, kind: str, warnings: list[str]) -> list[TimedLine]:
    out = []
    for x in lines:
        if x.start >= duration - 0.05:
            warnings.append(f"Bỏ {kind} “{x.text[:30]}” vì video mới chỉ dài {duration:.1f}s")
            continue
        if x.end > duration:
            warnings.append(f"Đã cắt {kind} “{x.text[:30]}” cho vừa video {duration:.1f}s")
            x = x.model_copy(update={"end": round(duration, 2)})
        out.append(x)
    return out


def copy_settings(src_id: str, dst_id: str) -> tuple[Template, list[str]]:
    """Chép chữ, lời thoại, kiểu chữ, vùng che, âm thanh từ video này sang video khác.

    Vị trí/cỡ chữ và vùng che co giãn theo độ phân giải video mới. Trả về (template đã lưu, cảnh báo).
    """
    src, dst = load_template(src_id), load_template(dst_id)
    warnings: list[str] = []
    kx, ky = dst.width / src.width, dst.height / src.height
    st = src.style
    style = st.model_copy(update={
        "size": max(10, min(300, round(st.size * ky))), "outline": min(20.0, round(st.outline * ky, 1)),
        "center_x": min(round(st.center_x * kx), dst.width), "center_y": min(round(st.center_y * ky), dst.height),
        "max_width": max(1, round(st.max_width * kx))})
    cover = None
    if src.cover:
        c = src.cover
        x, y = min(round(c.x * kx), dst.width - 1), min(round(c.y * ky), dst.height - 1)
        cover = Box(x=x, y=y, w=max(1, min(round(c.w * kx), dst.width - x)),
                    h=max(1, min(round(c.h * ky), dst.height - y)))
    tdir, ddir = template_dir(src_id), template_dir(dst_id)
    files = {}
    for key, stem in (("music", "music"), ("voice_file", "voiceover")):
        name = getattr(src, key)
        if name and (tdir / name).is_file():
            for old in ddir.glob(f"{stem}.*"):
                old.unlink()
            shutil.copy2(tdir / name, ddir / name)
            files[key] = name
        else:
            files[key] = getattr(dst, key)
    tpl = dst.model_copy(update={
        "app": src.app, "concept": src.concept, "source_lang": src.source_lang, "glossary": list(src.glossary),
        "captions": _scaled_lines(src.captions, dst.duration, "caption", warnings),
        "voice": _scaled_lines(src.voice, dst.duration, "câu thoại", warnings),
        "style": style, "cover": cover, "cover_mode": src.cover_mode, "audio_mode": src.audio_mode,
        "voice_offset": src.voice_offset, **files})
    return save_template(Template.model_validate(tpl.model_dump())), warnings


def save_template(tpl: Template) -> Template:
    write_json(template_dir(tpl.id) / "template.json", tpl.model_dump(mode="json"))
    return tpl


def load_template(tid: str) -> Template:
    data = read_json(template_dir(tid) / "template.json")
    if data is None:
        raise FileNotFoundError("Không tìm thấy template")
    return Template.model_validate(data)


def list_templates() -> list[Template]:
    root = D.DATA_DIR / "templates"
    out = []
    files = sorted(root.glob("*/template.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []
    for f in files:
        try:
            out.append(Template.model_validate(read_json(f)))
        except ValueError:
            continue
    return out


def delete_template(tid: str) -> None:
    shutil.rmtree(template_dir(tid), ignore_errors=True)


def set_music(tid: str, src: Path) -> Template:
    ext = src.suffix.lower()
    if ext not in AUDIO_EXT:
        raise ValueError(f"File nhạc {ext} chưa hỗ trợ — dùng MP3/WAV/M4A.")
    tpl = load_template(tid)
    for old in template_dir(tid).glob("music.*"):
        old.unlink()
    shutil.copy2(src, template_dir(tid) / f"music{ext}")
    tpl.music = f"music{ext}"
    tpl.audio_mode = "music_file"
    return save_template(tpl)


def set_voice_file(tid: str, src: Path) -> Template:
    """Lưu file voice người dùng tự tải lên; nhạc nền vẫn lấy từ video gốc (tách giọng gốc ra)."""
    ext = src.suffix.lower()
    if ext not in AUDIO_EXT:
        raise ValueError(f"File voice {ext} chưa hỗ trợ — dùng MP3/WAV/M4A.")
    tpl = load_template(tid)
    for old in template_dir(tid).glob("voiceover.*"):
        old.unlink()
    shutil.copy2(src, template_dir(tid) / f"voiceover{ext}")
    tpl.voice_file = f"voiceover{ext}"
    tpl.audio_mode = "uploaded_voice"
    return save_template(tpl)


def new_batch(template: Template) -> tuple[str, Path]:
    bid = datetime.now().strftime("%Y%m%d%H%M%S") + new_id()[:6]
    d = batch_dir(bid)
    d.mkdir(parents=True)
    write_json(d / "batch.json", {"id": bid, "template_id": template.id, "template_name": template.name,
                                  "created": datetime.now().isoformat(timespec="seconds")})
    return bid, d


def save_result(bid: str, res: JobResult) -> None:
    write_json(batch_dir(bid) / "results.json", res.model_dump(mode="json"))


def list_batches() -> list[dict]:
    root = D.DATA_DIR / "batches"
    out = []
    for d in sorted(root.iterdir(), reverse=True) if root.exists() else []:
        meta = read_json(d / "batch.json")
        if meta:
            meta["results"] = read_json(d / "results.json")
            out.append(meta)
    return out


MAX_DRAFT = 2_000_000  # byte — chữ + bản dịch của 1 phiên, dư sức cho vài chục ngôn ngữ


def _draft_path(did: str) -> Path:
    return D.DATA_DIR / "drafts" / f"{_check_id(did)}.json"


def save_draft(did: str, data: dict) -> None:
    """Lưu phiên làm việc (nhóm video, ngôn ngữ, bản dịch…) để tải lại trang hay mở lại tool không bị mất."""
    path = _draft_path(did)
    size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    if size > MAX_DRAFT:
        raise ValueError(f"Bản nháp quá lớn ({size // 1024} KB) — bớt ngôn ngữ/hook rồi thử lại")
    write_json(path, data)


def load_draft(did: str) -> dict | None:
    return read_json(_draft_path(did))


def delete_draft(did: str) -> None:
    _draft_path(did).unlink(missing_ok=True)
