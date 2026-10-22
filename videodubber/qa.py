"""Kiểm tra tự động cho mỗi video ra. Mỗi check là một câu người dùng hiểu được."""
from __future__ import annotations

import shutil
import subprocess
import unicodedata
from pathlib import Path

from .audio import MAX_SPEED, TARGET_LUFS, Fit
from .captions import Layout, glyphs_in_font
from .media import loudness, probe
from .models import QACheck, Template


def check_duration(out: Path, tpl: Template) -> QACheck:
    info = probe(out)
    frame = 1.0 / (tpl.fps or 30)
    ok = abs(info.duration - tpl.duration) <= frame + 1e-3
    return QACheck(name="Thời lượng", ok=ok, detail=f"{info.duration:.2f}s (gốc {tpl.duration:.2f}s)")


def check_voice(fits: list[Fit]) -> QACheck:
    if not fits:
        return QACheck(name="Tốc độ voice", ok=True, detail="không đổi voice")
    bad = [f for f in fits if f.too_long]
    top = max(f.natural / f.slot for f in fits)
    if bad:
        idx = ", ".join(str(f.index + 1) for f in bad)
        return QACheck(name="Tốc độ voice", ok=False,
                       detail=f"Câu {idx} dài quá (cần {top:.2f}× > {MAX_SPEED}×) — rút gọn câu dịch rồi render lại")
    return QACheck(name="Tốc độ voice", ok=True, detail=f"nhanh nhất {top:.2f}×")


def check_layout(layouts: list[Layout]) -> QACheck:
    bad = [i + 1 for i, lay in enumerate(layouts) if not lay.fits]
    if bad:
        return QACheck(name="Caption vừa khung", ok=False,
                       detail=f"Caption {', '.join(map(str, bad))} quá dài, chữ bị thu nhỏ nhiều — nên rút gọn")
    worst = min((lay.scale for lay in layouts), default=1.0)
    return QACheck(name="Caption vừa khung", ok=True, detail=f"cỡ chữ ≥ {worst:.0%} bản gốc")


def _system_has_glyph(ch: str) -> bool | None:
    """Hỏi fontconfig có font nào chứa ký tự không; None nếu máy không có fc-list (Windows)."""
    exe = shutil.which("fc-list")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, f":charset={ord(ch):x}", "family"], capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return None
    return bool(out.stdout.strip())


def check_glyphs(texts: list[str], font: str, uppercase: bool) -> QACheck:
    have = glyphs_in_font(font) or set()
    chars = {c for t in texts for c in (t.upper() if uppercase else t)
             if not c.isspace() and unicodedata.category(c)[0] != "C"}
    missing = []
    unknown = False
    for c in sorted(chars):
        if ord(c) in have:
            continue
        sys_ok = _system_has_glyph(c)
        if sys_ok is None:
            unknown = True
        elif not sys_ok:
            missing.append(c)
    if missing:
        return QACheck(name="Font đủ chữ", ok=False,
                       detail=f"Thiếu font cho: {' '.join(missing[:12])} — cài bộ Noto Sans cho ngôn ngữ này")
    return QACheck(name="Font đủ chữ", ok=True, detail="không kiểm được font hệ thống" if unknown else "đủ")


def check_loudness(out: Path, remixed: bool) -> QACheck:
    if not remixed:
        return QACheck(name="Âm lượng", ok=True, detail="giữ âm gốc")
    lufs = loudness(out)
    if lufs is None:
        return QACheck(name="Âm lượng", ok=False, detail="video không có tiếng")
    ok = abs(lufs - TARGET_LUFS) <= 1.0
    return QACheck(name="Âm lượng", ok=ok, detail=f"{lufs:.1f} LUFS (chuẩn {TARGET_LUFS:.0f} ±1)")


def check_glossary(glossary: list[str], source: list[str], target: list[str]) -> QACheck:
    """Từ không dịch (tên app, tính năng): có trong bản gốc thì bản dịch cũng phải có."""
    src, dst = " ".join(source).casefold(), " ".join(target).casefold()
    lost = [g for g in glossary if g.strip() and g.casefold() in src and g.casefold() not in dst]
    if lost:
        return QACheck(name="Glossary", ok=False, detail=f"Bản dịch làm mất: {', '.join(lost)}")
    return QACheck(name="Glossary", ok=True, detail=f"{len(glossary)} từ" if glossary else "chưa khai báo")
