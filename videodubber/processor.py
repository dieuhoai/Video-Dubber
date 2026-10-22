"""Nghiệp vụ chính: 1 template × N biến thể (ngôn ngữ × câu hook) → N video MP4 + QA.

Nguyên tắc: hàm thuần, không print, không import web; lỗi 1 video không dừng cả batch;
báo tiến độ qua `on_progress(done, total, item)`; huỷ qua `should_stop()`.
"""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import store
from .audio import Fit, fit_clip, mix, separate_music, slots
from .captions import build_ass
from .io_utils import atomic_write_text
from .langs import get_lang
from .media import MediaError
from .models import BatchRequest, ItemResult, JobResult, LangVariant, Template
from .qa import check_duration, check_glossary, check_glyphs, check_layout, check_loudness, check_voice
from .render import render
from .tts import TTS, default_tts

Progress = Callable[[int, int, ItemResult], None]
Stage = Callable[[str], None]
log = logging.getLogger("videodubber")


def _stage(cb: Stage | None, text: str) -> None:
    """Báo bước đang làm lên giao diện + ghi nhật ký (để biết tool đang chạy hay bị kẹt ở đâu)."""
    log.info(text)
    if cb:
        cb(text)


def output_name(tpl: Template, v: LangVariant, version: int, ratio: str = "9x16") -> str:
    voice = f"{v.gender}1" if tpl.uses_voice else "orig"
    lang = re.sub(r"[^a-z0-9]", "", v.lang.lower())
    return f"{tpl.app}_{tpl.concept}_{lang}_{voice}_{v.hook}_{ratio}_v{version}.mp4"


def validate_variant(tpl: Template, v: LangVariant) -> None:
    get_lang(v.lang)
    if len(v.captions) != len(tpl.captions):
        raise ValueError(f"[{v.lang} {v.hook}] cần {len(tpl.captions)} câu caption, đang có {len(v.captions)}")
    if any(not c.strip() for c in v.captions):
        raise ValueError(f"[{v.lang} {v.hook}] còn caption trống")
    if tpl.uses_voice:
        if len(v.voice) != len(tpl.voice):
            raise ValueError(f"[{v.lang} {v.hook}] cần {len(tpl.voice)} câu thoại, đang có {len(v.voice)}")
        if any(not c.strip() for c in v.voice):
            raise ValueError(f"[{v.lang} {v.hook}] còn câu thoại trống")


def prepare_music(tpl: Template, tdir: Path) -> Path | None:
    """Chạy 1 lần cho mỗi template (kết quả tách nhạc được giữ lại để dùng cho các batch sau)."""
    if tpl.audio_mode == "music_file":
        if not tpl.music or not (tdir / tpl.music).is_file():
            raise MediaError("Chưa có file nhạc nền — tải nhạc lên ở bước Template.")
        return tdir / tpl.music
    if tpl.audio_mode == "separate":
        cached = tdir / "stems" / "music.wav"
        return cached if cached.is_file() else separate_music(tdir / tpl.video, tdir / "stems")
    return None


def render_variant(tpl: Template, tdir: Path, v: LangVariant, out: Path, music: Path | None, tts: TTS,
                   work: Path, on_stage: Stage | None = None) -> ItemResult:
    lang = get_lang(v.lang)
    work.mkdir(parents=True, exist_ok=True)
    ass_text, layouts = build_ass(tpl.captions, v.captions, tpl.style, tpl.width, tpl.height, lang.spaces)
    ass = work / "captions.ass"
    atomic_write_text(ass, ass_text)

    fits: list[Fit] = []
    audio = None
    if tpl.uses_voice:
        sl = slots([x.start for x in tpl.voice], [x.end for x in tpl.voice], tpl.duration)
        clips = []
        for i, (line, text) in enumerate(zip(tpl.voice, v.voice, strict=True)):
            _stage(on_stage, f"{v.lang} {v.hook}: tạo giọng câu {i + 1}/{len(tpl.voice)}")
            raw = tts.synth(text.strip(), lang, v.gender, work / f"tts_{i}.wav")
            f = fit_clip(raw, work / f"fit_{i}.wav", i, sl[i])
            fits.append(f)
            clips.append((work / f"fit_{i}.wav", line.start))
        _stage(on_stage, f"{v.lang} {v.hook}: trộn giọng + nhạc")
        audio = mix(clips, music, tpl.duration, work / "mix.wav")
    elif tpl.audio_mode == "music_file" or tpl.audio_mode == "separate":
        audio = mix([], music, tpl.duration, work / "mix.wav")

    _stage(on_stage, f"{v.lang} {v.hook}: xuất video")
    render(tdir / tpl.video, ass, out, tpl.duration, tpl.cover, tpl.captions, audio,
           keep_original_audio=tpl.audio_mode == "original", workdir=work, size=(tpl.width, tpl.height))
    _stage(on_stage, f"{v.lang} {v.hook}: kiểm tra")
    checks = [
        check_duration(out, tpl),
        check_layout(layouts),
        check_glyphs(v.captions, tpl.style.font, tpl.style.uppercase),
        check_voice(fits),
        check_loudness(out, remixed=audio is not None),
        check_glossary(tpl.glossary, [x.text for x in tpl.captions + tpl.voice], v.captions + v.voice),
    ]
    return ItemResult(lang=f"{v.lang} {v.hook}", output=out, ok=True, checks=checks)


def run_batch(req: BatchRequest, on_progress: Progress | None = None, should_stop: Callable[[], bool] | None = None,
              tts: TTS | None = None, batch: tuple[str, Path] | None = None,
              on_stage: Stage | None = None) -> JobResult:
    tpl = store.load_template(req.template_id)
    tdir = store.template_dir(tpl.id)
    for v in req.variants:  # báo lỗi nhập liệu trước khi tốn thời gian render
        validate_variant(tpl, v)
    names = [output_name(tpl, v, req.version, req.ratio) for v in req.variants]
    if len(set(names)) != len(names):
        raise ValueError("Có 2 biến thể trùng ngôn ngữ + giọng + mã hook — đổi mã hook (h1, h2…) cho khác nhau.")
    bid, bdir = batch or store.new_batch(tpl)
    if tpl.audio_mode == "separate" and not (tdir / "stems" / "music.wav").is_file():
        _stage(on_stage, "Tách nhạc nền khỏi giọng gốc (chỉ lần đầu, 15–90 giây)")
    music = prepare_music(tpl, tdir)
    if tpl.uses_voice:
        _stage(on_stage, "Nạp giọng đọc AI (vài giây đến nửa phút)")
    tts = tts or default_tts()
    results: list[ItemResult] = []
    with tempfile.TemporaryDirectory(prefix="vdub_") as tmp:
        for i, (v, name) in enumerate(zip(req.variants, names, strict=True), 1):
            if should_stop and should_stop():
                break
            try:
                r = render_variant(tpl, tdir, v, bdir / name, music, tts, Path(tmp) / f"{i}", on_stage)
            except Exception as e:  # noqa: BLE001 — lỗi 1 video không được làm hỏng cả batch
                log.exception("Lỗi khi tạo %s %s", v.lang, v.hook)
                r = ItemResult(lang=f"{v.lang} {v.hook}", ok=False, error=str(e))
            finally:
                shutil.rmtree(Path(tmp) / f"{i}", ignore_errors=True)
            results.append(r)
            if on_progress:
                on_progress(i, len(req.variants), r)
    res = JobResult(batch_id=bid, items=results)
    store.save_result(bid, res)
    return res
