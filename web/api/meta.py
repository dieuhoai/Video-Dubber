"""Thông tin cho giao diện: ngôn ngữ, khả năng của máy chủ, trợ giúp dịch."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from videodubber import modelstore, store
from videodubber.audio import SEPARATION_MODEL
from videodubber.langs import LANGS
from videodubber.translate import api_available, build_prompt, parse_reply, translate_with_api
from videodubber.tts import KokoroTTS

router = APIRouter(prefix="/api")


@router.get("/langs")
def langs() -> dict:
    return {"items": [lang.to_dict() for lang in LANGS.values()]}


@router.get("/log", response_class=PlainTextResponse)
def log_tail(lines: int = 200) -> str:
    """200 dòng nhật ký cuối — để người dùng gửi khi tool báo lỗi hoặc bị kẹt."""
    from videodubber import defaults as D
    f = D.USER_DIR / "videodubber.log"
    if not f.is_file():
        return "Chưa có nhật ký."
    return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(lines, 2000)):])


_dl: dict = {"running": False, "name": "", "done": 0, "total": 0, "error": None}
_dl_lock = threading.Lock()


@router.get("/capabilities")
def capabilities() -> dict:
    libs = modelstore.missing_libs()
    return {"offline_voice": KokoroTTS.available() and not libs,
            "separate": modelstore.find_model(SEPARATION_MODEL) is not None and not libs,
            "translate_api": api_available(), "missing_models": modelstore.missing(), "missing_libs": libs,
            "download": dict(_dl)}


def _download() -> None:
    try:
        modelstore.download_all(lambda name, done, total: _dl.update(name=name, done=done, total=total))
        _dl.update(error=None)
    except Exception as e:  # noqa: BLE001 — mất mạng, hết dung lượng… báo lên giao diện
        logging.getLogger("videodubber").exception("Tải mô hình lỗi")
        _dl.update(error=f"Tải mô hình lỗi: {e}. Kiểm tra mạng rồi bấm lại.")
    finally:
        _dl.update(running=False)
        _dl_lock.release()


@router.post("/models/download")
def download_models() -> dict:
    if not modelstore.missing():
        return {"started": False, "missing": []}
    if not _dl_lock.acquire(blocking=False):
        return {"started": False, "running": True}
    _dl.update(running=True, error=None, name="", done=0, total=0)
    threading.Thread(target=_download, daemon=True).start()
    return {"started": True}


@router.post("/translate/prompt")
def prompt(body: dict) -> dict:
    try:
        tpl = store.load_template(str(body.get("template_id", "")))
        return {"prompt": build_prompt(tpl, list(body.get("langs") or []), int(body.get("hooks") or 1))}
    except FileNotFoundError as e:
        raise HTTPException(404, "Không tìm thấy template") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/translate/parse")
def parse(body: dict) -> dict:
    try:
        return {"result": parse_reply(str(body.get("text", "")))}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/translate/auto")
def auto(body: dict) -> dict:
    try:
        tpl = store.load_template(str(body.get("template_id", "")))
        text = translate_with_api(build_prompt(tpl, list(body.get("langs") or []), int(body.get("hooks") or 1)))
        return {"result": parse_reply(text)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Không tìm thấy template") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
