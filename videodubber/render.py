"""Ghép hình: làm mờ caption cũ (viền mờ dần), vẽ caption mới (ASS), gắn âm thanh, giữ đúng thời lượng."""
from __future__ import annotations

from pathlib import Path

from .captions import fonts_dir
from .media import ffmpeg
from .models import Box, TimedLine


def feather_mask(box: Box, out: Path) -> Path:
    """Mặt nạ xám: giữa trắng, mép trên/dưới mờ dần — để vùng làm mờ hoà vào nền, không lộ khung chữ nhật.

    Không làm mờ dần 2 bên: caption thường kéo gần hết bề ngang, mép trái/phải mờ dần sẽ lộ chữ cũ.
    """
    f = max(min(box.h // 5, 50), 4)
    ffmpeg("-f", "lavfi", "-i", f"color=black:s={box.w}x{box.h}:d=0.04", "-vf",
           f"drawbox=x=0:y={f}:w={box.w}:h={max(box.h - 2 * f, 1)}:"
           f"color=white:t=fill,boxblur={f}:2,format=gray", "-frames:v", "1", str(out), timeout=60)
    return out


def _enable(lines: list[TimedLine]) -> str:
    return "+".join(f"between(t,{x.start:.3f},{x.end:.3f})" for x in lines) or "0"


def _filter_path(p: Path) -> str:
    """Escape đường dẫn cho filter ass= (Windows có ':' và '\\')."""
    s = p.resolve().as_posix()
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def render(video: Path, ass: Path, out: Path, duration: float, cover: Box | None, captions: list[TimedLine],
           audio: Path | None, keep_original_audio: bool, workdir: Path) -> Path:
    """Xuất MP4 H.264/AAC. Thời lượng luôn = video gốc."""
    args = ["-i", str(video)]
    parts: list[str] = []
    last = "0:v"
    if cover and captions:
        mask = feather_mask(cover, workdir / "mask.png")
        args += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(mask)]
        blur = max(min(cover.h // 6, 40), 4)
        parts += [
            "[0:v]split[base][src]",
            f"[src]crop={cover.w}:{cover.h}:{cover.x}:{cover.y},boxblur={blur}:4,format=yuva420p[bl]",
            "[1:v]format=gray[m]", "[bl][m]alphamerge[patch]",
            f"[base][patch]overlay={cover.x}:{cover.y}:eof_action=pass:enable='{_enable(captions)}'[cov]",
        ]
        last = "cov"
    parts.append(f"[{last}]ass=filename='{_filter_path(ass)}':fontsdir='{_filter_path(fonts_dir())}',"
                 "format=yuv420p[vout]")
    amap: list[str]
    if audio is not None:
        idx = 2 if cover and captions else 1
        args += ["-i", str(audio)]
        amap = ["-map", f"{idx}:a:0"]
    elif keep_original_audio:
        amap = ["-map", "0:a:0?"]
    else:
        amap = []
    ffmpeg(*args, "-filter_complex", ";".join(parts), "-map", "[vout]", *amap,
           "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out), timeout=1800)
    return out


def preview_frame(video: Path, t: float, ass: Path, cover: Box | None, out: Path, workdir: Path) -> Path:
    """Ảnh xem trước 1 khung hình với caption mới (ass phải có câu chạy từ 0s) — để chỉnh vị trí/kiểu chữ nhanh."""
    args = ["-ss", f"{max(t, 0):.3f}", "-i", str(video)]
    parts: list[str] = []
    last = "0:v"
    if cover:
        mask = feather_mask(cover, workdir / "mask.png")
        args += ["-i", str(mask)]
        blur = max(min(cover.h // 6, 40), 4)
        parts += ["[0:v]split[base][src]",
                  f"[src]crop={cover.w}:{cover.h}:{cover.x}:{cover.y},boxblur={blur}:4,format=yuva420p[bl]",
                  "[1:v]format=gray[m]", "[bl][m]alphamerge[patch]",
                  f"[base][patch]overlay={cover.x}:{cover.y}[cov]"]
        last = "cov"
    parts.append(f"[{last}]ass=filename='{_filter_path(ass)}':fontsdir='{_filter_path(fonts_dir())}'[vout]")
    ffmpeg(*args, "-filter_complex", ";".join(parts), "-map", "[vout]", "-frames:v", "1", "-q:v", "3", str(out),
           timeout=60)
    return out
