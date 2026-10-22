"""Dựng file phụ đề ASS cho caption mới: tự xuống dòng, tự giảm cỡ chữ, glow nhiều lớp."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .defaults import resource_root
from .models import CaptionStyle, TimedLine

MIN_SCALE = 0.7  # nhỏ hơn 70% cỡ chữ gốc thì coi là "câu quá dài" (QA báo đỏ)


def fonts_dir() -> Path:
    return resource_root() / "fonts"


@lru_cache(maxsize=8)
def _metrics(font: str) -> tuple[dict[int, int], int] | None:
    """(cmap→advance, đơn vị chia) của font đóng kèm; None nếu không có file (dùng ước lượng).

    libass coi Fontsize = winAscent + winDescent (không phải em), nên chia theo tổng này để đo khớp với lúc vẽ.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    for f in sorted(fonts_dir().glob("*.[ot]tf")):
        tt = TTFont(str(f), lazy=True)
        if tt["name"].getBestFamilyName() != font:
            continue
        hmtx, cmap = tt["hmtx"], tt.getBestCmap()
        os2 = tt["OS/2"] if "OS/2" in tt else None
        height = (os2.usWinAscent + os2.usWinDescent) if os2 else tt["head"].unitsPerEm
        return {cp: hmtx[g][0] for cp, g in cmap.items()}, height
    return None


def glyphs_in_font(font: str) -> set[int] | None:
    m = _metrics(font)
    return set(m[0]) if m else None


def text_width(text: str, font: str, size: float) -> float:
    m = _metrics(font)
    total = 0.0
    for ch in text:
        if m and ord(ch) in m[0]:
            total += m[0][ord(ch)] / m[1]
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            total += 0.8
        else:
            total += 0.5
    return total * size


def _tokens(text: str, spaces: bool) -> list[str]:
    if spaces:
        return text.split()
    return list(text.replace(" ", "　" if not text.isascii() else " "))


def wrap(text: str, font: str, size: float, max_width: float, spaces: bool = True) -> list[str]:
    """Ngắt dòng tham lam theo độ rộng thật của chữ. Dòng có ký tự xuống dòng của người dùng được giữ."""
    lines: list[str] = []
    joiner = " " if spaces else ""
    for para in text.splitlines() or [""]:
        cur = ""
        for tok in _tokens(para.strip(), spaces):
            cand = f"{cur}{joiner}{tok}" if cur else tok
            if cur and text_width(cand, font, size) > max_width:
                lines.append(cur)
                cur = tok
            else:
                cur = cand
        if cur:
            lines.append(cur)
    return lines


def _balance(lines: list[str], font: str, size: float, max_width: float, spaces: bool) -> list[str]:
    """2 dòng lệch nhau quá nhiều (vd 5 từ + 1 từ) → chia lại cho đều, giống caption dựng tay."""
    if len(lines) != 2 or not spaces:
        return lines
    words = " ".join(lines).split()
    best = lines
    best_diff = abs(text_width(lines[0], font, size) - text_width(lines[1], font, size))
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = text_width(a, font, size), text_width(b, font, size)
        if max(wa, wb) <= max_width and abs(wa - wb) < best_diff:
            best, best_diff = [a, b], abs(wa - wb)
    return best


@dataclass
class Layout:
    lines: list[str]
    size: int
    scale: float

    @property
    def fits(self) -> bool:
        return self.scale >= MIN_SCALE


def layout(text: str, style: CaptionStyle, spaces: bool = True) -> Layout:
    """Giảm dần cỡ chữ tới khi ≤ max_lines dòng; dừng ở 50% để chữ không quá bé."""
    if style.uppercase:
        text = text.upper()
    size = float(style.size)
    while True:
        lines = wrap(text, style.font, size, style.max_width, spaces)
        if len(lines) <= style.max_lines or size <= style.size * 0.5:
            lines = _balance(lines, style.font, size, style.max_width, spaces)
            return Layout(lines, round(size), round(size / style.size, 2))
        size *= 0.94


def _ass_color(hex_rgb: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _tag_color(hex_rgb: str) -> str:
    return f"&H{hex_rgb[5:7]}{hex_rgb[3:5]}{hex_rgb[1:3]}&".upper()


def _lighten(hex_rgb: str, k: float = 0.5) -> str:
    """Pha màu với trắng — lớp glow trong sáng hơn lớp ngoài, giống hiệu ứng neon."""
    rgb = [int(hex_rgb[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * k):02X}" for c in rgb)


def _ts(t: float) -> str:
    cs = round(t * 100)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(lines: list[TimedLine], texts: list[str], style: CaptionStyle, width: int, height: int,
              spaces: bool = True) -> tuple[str, list[Layout]]:
    """Trả về nội dung .ass và layout từng câu (để QA kiểm tra câu có vừa khung không)."""
    if len(texts) != len(lines):
        raise ValueError(f"Cần {len(lines)} câu caption, nhận {len(texts)}")
    st = style
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Glow,{st.font},{st.size},{_ass_color(st.glow_color)},&H00000000,{_ass_color(st.glow_color)},"
        "&H00000000,1,0,0,0,100,100,0,0,1,22,0,5,0,0,0,1",
        f"Style: Text,{st.font},{st.size},{_ass_color(st.text_color)},&H00000000,{_ass_color(st.outline_color)},"
        f"&H00000000,1,0,0,0,100,100,0,0,1,{st.outline:g},0,5,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events: list[str] = []
    layouts: list[Layout] = []
    for line, txt in zip(lines, texts, strict=True):
        lay = layout(txt, st, spaces)
        layouts.append(lay)
        body = r"\N".join(_escape(x) for x in lay.lines)
        pos = rf"\pos({st.center_x},{st.center_y})\fs{lay.size}"
        a, b = _ts(line.start), _ts(line.end)
        if st.glow:
            k = lay.size / st.size
            events.append(f"Dialogue: 0,{a},{b},Glow,,0,0,0,,{{{pos}\\blur{28 * k:.0f}\\bord{30 * k:.0f}}}{body}")
            events.append(f"Dialogue: 0,{a},{b},Glow,,0,0,0,,{{{pos}\\blur{28 * k:.0f}\\bord{30 * k:.0f}}}{body}")
            events.append(f"Dialogue: 1,{a},{b},Glow,,0,0,0,,{{{pos}\\blur{14 * k:.0f}\\bord{12 * k:.0f}"
                          f"\\3c{_tag_color(_lighten(st.glow_color))}}}{body}")
        events.append(f"Dialogue: 2,{a},{b},Text,,0,0,0,,{{{pos}}}{body}")
    return "\n".join(head + events) + "\n", layouts
