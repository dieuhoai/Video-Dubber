"""Thông tin cho giao diện: ngôn ngữ, khả năng của máy chủ, trợ giúp dịch."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from videodubber import store
from videodubber.audio import SEPARATION_MODEL
from videodubber.defaults import models_dir
from videodubber.langs import LANGS
from videodubber.translate import api_available, build_prompt, parse_reply, translate_with_api
from videodubber.tts import KokoroTTS

router = APIRouter(prefix="/api")


@router.get("/langs")
def langs() -> dict:
    return {"items": [lang.to_dict() for lang in LANGS.values()]}


@router.get("/capabilities")
def capabilities() -> dict:
    return {"offline_voice": KokoroTTS.available(), "separate": (models_dir() / SEPARATION_MODEL).is_file(),
            "translate_api": api_available()}


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
