"""Nghiệp vụ chính: 1 template × N biến thể (ngôn ngữ × câu hook) → N video MP4 + QA.

Nguyên tắc: hàm thuần, không print, không import web; lỗi 1 video không dừng cả batch;
báo tiến độ qua `on_progress(done, total, item)`; huỷ qua `should_stop()`.
"""
from __future__ import annotations

import hashlib
import logging
import re
import shutil
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path

from . import defaults as D
from . import store
from .audio import Fit, fit_clip, mix, separate_music, slots
from .captions import build_ass
from .clean import clean_clip
from .io_utils import atomic_write_text
from .langs import get_lang
from .media import MediaError, audio_duration, ffmpeg
from .models import BatchRequest, ItemResult, JobResult, LangVariant, QACheck, Template
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


def output_name(tpl: Template, v: LangVariant, version: int, ratio: str = "9x16", tag: str = "") -> str:
    voice = f"{v.gender}1" if tpl.uses_voice else ("up" if tpl.audio_mode == "uploaded_voice" else "orig")
    lang = re.sub(r"[^a-z0-9]", "", v.lang.lower())
    tag = f"_{tag}" if tag else ""
    return f"{tpl.app}_{tpl.concept}{tag}_{lang}_{voice}_{v.hook}_{ratio}_v{version}.mp4"


def video_tags(tpls: list[Template]) -> list[str]:
    """Tên ngắn (không dấu) của từng video để tên file trong batch nhiều video không trùng nhau."""
    if len(tpls) < 2:
        return [""]
    tags: list[str] = []
    for i, t in enumerate(tpls, 1):
        base = unicodedata.normalize("NFKD", t.name.replace("đ", "d").replace("Đ", "D"))
        tag = re.sub(r"[^A-Za-z0-9]+", "-", base.encode("ascii", "ignore").decode()).strip("-").lower()[:30]
        tag = tag or f"video{i}"
        tags.append(f"{tag}-{i}" if tag in tags else tag)
    return tags


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
    if tpl.audio_mode == "uploaded_voice" and (not tpl.voice_file or not (tdir / tpl.voice_file).is_file()):
        raise MediaError("Chưa tải file voice lên — chọn file ở bước 1, mục Âm thanh.")
    if tpl.audio_mode in ("separate", "uploaded_voice"):
        cached = tdir / "stems" / "music.wav"
        return cached if cached.is_file() else separate_music(tdir / tpl.video, tdir / "stems")
    return None


def prepare_clean(tpl: Template, tdir: Path, on_stage: Stage | None = None) -> tuple[Path, float] | None:
    """Xoá riêng nét chữ cũ (1 lần cho mỗi template + khung che, có cache). None → làm mờ cả khung như cũ."""
    if tpl.cover_mode != "text" or not tpl.cover or not tpl.captions:
        return None
    _stage(on_stage, "Xoá chữ cũ, giữ nền (chỉ lần đầu)")
    try:
        res = clean_clip(tdir / tpl.video, tpl.cover, tpl.captions, tpl.fps, tdir / "clean")
    except MediaError:
        log.exception("Không xoá riêng được chữ cũ — dùng cách làm mờ cả khung")
        return None
    if res is None:
        log.info("Không tách được chữ cũ khỏi nền (nền đứng yên?) — dùng cách làm mờ cả khung")
    return res


def _synth_cached(tts: TTS, text: str, lang, gender: str, out: Path) -> Path:
    """Giọng đọc đã tạo cho cùng (engine, ngôn ngữ, giọng, câu) thì lấy lại từ bộ nhớ đệm — không đọc lại."""
    key = hashlib.sha1(f"{tts.name}|{lang.code}|{gender}|{text}".encode()).hexdigest()[:24]
    cache_dir = D.DATA_DIR / "tts_cache"
    cached = cache_dir / f"{key}.wav"
    if cached.is_file():
        shutil.copyfile(cached, out)
        return out
    tts.synth(text, lang, gender, out)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".part")
        shutil.copyfile(out, tmp)
        tmp.replace(cached)
    except OSError:
        log.warning("Không ghi được bộ nhớ đệm giọng đọc (vẫn dùng bình thường)")
    return out


def render_variant(tpl: Template, tdir: Path, v: LangVariant, out: Path, music: Path | None, tts: TTS,
                   work: Path, on_stage: Stage | None = None, clean: tuple[Path, float] | None = None) -> ItemResult:
    lang = get_lang(v.lang)
    work.mkdir(parents=True, exist_ok=True)
    ass_text, layouts = build_ass(tpl.captions, v.captions, tpl.style, tpl.width, tpl.height, lang.spaces)
    ass = work / "captions.ass"
    atomic_write_text(ass, ass_text)

    fits: list[Fit] = []
    audio = None
    upload_check: QACheck | None = None
    if tpl.uses_voice:
        sl = slots([x.start for x in tpl.voice], [x.end for x in tpl.voice], tpl.duration)
        clips = []
        for i, (line, text) in enumerate(zip(tpl.voice, v.voice, strict=True)):
            _stage(on_stage, f"{v.lang} {v.hook}: tạo giọng câu {i + 1}/{len(tpl.voice)}")
            raw = _synth_cached(tts, text.strip(), lang, v.gender, work / f"tts_{i}.wav")
            f = fit_clip(raw, work / f"fit_{i}.wav", i, sl[i])
            fits.append(f)
            clips.append((work / f"fit_{i}.wav", line.start))
        _stage(on_stage, f"{v.lang} {v.hook}: trộn giọng + nhạc")
        audio = mix(clips, music, tpl.duration, work / "mix.wav")
    elif tpl.audio_mode == "uploaded_voice":
        _stage(on_stage, f"{v.lang} {v.hook}: ghép voice tải lên + nhạc nền")
        slot = max(tpl.duration - tpl.voice_offset, 0.1)
        nat = audio_duration(tdir / tpl.voice_file)
        clip = work / "voice_up.wav"
        # Không tua nhanh giọng người dùng: dài quá thì cắt ở cuối video (fade 60 ms) và báo đỏ.
        ffmpeg("-i", str(tdir / tpl.voice_file), "-af",
               f"atrim=0:{slot:.3f},afade=t=out:st={max(slot - 0.06, 0):.3f}:d=0.06", "-ac", "1", "-ar", "44100",
               str(clip), timeout=120)
        upload_check = QACheck(name="Voice tải lên", ok=nat <= slot + 0.05,
                               detail=(f"{nat:.1f}s, vừa video" if nat <= slot + 0.05 else
                                       f"Voice dài {nat:.1f}s, video chỉ còn {slot:.1f}s — phần cuối bị cắt"))
        audio = mix([(clip, tpl.voice_offset)], music, tpl.duration, work / "mix.wav")
    elif tpl.audio_mode == "music_file" or tpl.audio_mode == "separate":
        audio = mix([], music, tpl.duration, work / "mix.wav")

    _stage(on_stage, f"{v.lang} {v.hook}: xuất video")
    render(tdir / tpl.video, ass, out, tpl.duration, tpl.cover, tpl.captions, audio,
           keep_original_audio=tpl.audio_mode == "original", workdir=work, size=(tpl.width, tpl.height),
           clean=clean)
    _stage(on_stage, f"{v.lang} {v.hook}: kiểm tra")
    checks = [
        check_duration(out, tpl),
        check_layout(layouts),
        check_glyphs(v.captions, tpl.style.font, tpl.style.uppercase),
        check_voice(fits),
        check_loudness(out, remixed=audio is not None),
        check_glossary(tpl.glossary, [x.text for x in tpl.captions + tpl.voice], v.captions + v.voice),
    ]
    if upload_check:
        checks.insert(3, upload_check)
    return ItemResult(lang=f"{v.lang} {v.hook}", output=out, ok=True, checks=checks)


def run_batch(req: BatchRequest, on_progress: Progress | None = None, should_stop: Callable[[], bool] | None = None,
              tts: TTS | None = None, batch: tuple[str, Path] | None = None,
              on_stage: Stage | None = None) -> JobResult:
    """Xuất mọi biến thể cho mọi video trong nhóm (1 video nếu không có template_ids) vào cùng 1 batch."""
    tpls = [store.load_template(tid) for tid in req.all_template_ids]
    tags = video_tags(tpls)
    plan: list[tuple[Template, str, list[str]]] = []
    for tpl, tag in zip(tpls, tags, strict=True):
        for v in req.variants:  # báo lỗi nhập liệu trước khi tốn thời gian render
            try:
                validate_variant(tpl, v)
            except ValueError as e:
                raise ValueError(f"Video “{tpl.name}”: {e}" if len(tpls) > 1 else str(e)) from e
        plan.append((tpl, tag, [output_name(tpl, v, req.version, req.ratio, tag) for v in req.variants]))
    names = [n for _, _, ns in plan for n in ns]
    if len(set(names)) != len(names):
        raise ValueError("Có 2 biến thể trùng ngôn ngữ + giọng + mã hook — đổi mã hook (h1, h2…) cho khác nhau.")
    bid, bdir = batch or store.new_batch(tpls[0])
    total = len(names)
    done = 0
    results: list[ItemResult] = []
    stopped = False
    for tpl, tag, tnames in plan:
        if stopped:
            break
        tdir = store.template_dir(tpl.id)
        stage = on_stage if len(tpls) < 2 else (lambda text, n=tpl.name: _cb(on_stage, f"[{n}] {text}"))
        if tpl.audio_mode in ("separate", "uploaded_voice") and not (tdir / "stems" / "music.wav").is_file():
            _stage(stage, "Tách nhạc nền khỏi giọng gốc (chỉ lần đầu, 15–90 giây)")
        music = prepare_music(tpl, tdir)
        clean = prepare_clean(tpl, tdir, stage)
        if tpl.uses_voice and tts is None:
            _stage(stage, "Nạp giọng đọc AI (vài giây đến nửa phút)")
            tts = default_tts()
        with tempfile.TemporaryDirectory(prefix="vdub_") as tmp:
            for i, (v, name) in enumerate(zip(req.variants, tnames, strict=True), 1):
                if should_stop and should_stop():
                    stopped = True
                    break
                label = f"{v.lang} {v.hook}" + (f" · {tag}" if tag else "")
                try:
                    r = render_variant(tpl, tdir, v, bdir / name, music, tts, Path(tmp) / f"{i}", stage, clean)
                    r.lang = label
                except Exception as e:  # noqa: BLE001 — lỗi 1 video không được làm hỏng cả batch
                    log.exception("Lỗi khi tạo %s", label)
                    r = ItemResult(lang=label, ok=False, error=str(e))
                finally:
                    shutil.rmtree(Path(tmp) / f"{i}", ignore_errors=True)
                results.append(r)
                done += 1
                if on_progress:
                    on_progress(done, total, r)
    res = JobResult(batch_id=bid, items=results)
    store.save_result(bid, res)
    return res


def _cb(cb: Stage | None, text: str) -> None:
    if cb:
        cb(text)
