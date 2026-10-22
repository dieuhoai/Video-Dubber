"""Ghép hình: xoá caption cũ (chỉ nét chữ, hoặc làm mờ cả khung), vẽ caption mới (ASS), gắn âm thanh."""
from __future__ import annotations

from pathlib import Path

from .captions import fonts_dir
from .media import ffmpeg, probe
from .models import Box, TimedLine


def feather_mask(box: Box, out: Path) -> Path:
    """Mặt nạ xám: giữa trắng, mép trên/dưới mờ dần — để vùng làm mờ hoà vào nền, không lộ khung chữ nhật.

    Không làm mờ dần 2 bên: caption thường kéo gần hết bề ngang, mép trái/phải mờ dần sẽ lộ chữ cũ.
    """
    f = max(min(box.h // 5, 50), 4)
    # Dốc mờ chỉ theo chiều dọc (geq) — boxblur cũ làm mờ cả 2 bên nên chữ cũ ở mép trái/phải lộ ra.
    ffmpeg("-f", "lavfi", "-i", f"color=black:s={box.w}x{box.h}:d=0.04", "-vf",
           f"format=gray,geq=lum='255*clip(min(Y\\,H-1-Y)/{f}\\,0\\,1)'", "-frames:v", "1", str(out), timeout=60)
    return out


def _cover_parts(cover: Box, width: int, height: int, enable: str | None) -> list[str]:
    """Xoá caption cũ: delogo tô lại vùng chữ từ các điểm ảnh viền ngoài (không còn nét chữ nào),
    làm mờ nhẹ cho mịn, rồi dán lại với mép trên/dưới mờ dần.

    Chỉ làm mờ (cách cũ) không đủ: chữ cũ dài hơn chữ mới sẽ lộ bóng ở 2 bên.
    """
    # delogo cần chừa ít nhất 1px quanh vùng xoá.
    x0, y0 = max(cover.x, 1), max(cover.y, 1)
    x1, y1 = min(cover.x + cover.w, width - 1), min(cover.y + cover.h, height - 1)
    blur = max(min(cover.h // 12, 20), 2)
    when = f":enable='{enable}'" if enable else ""
    return [
        "[0:v]split[base][src]",
        f"[src]delogo=x={x0}:y={y0}:w={max(x1 - x0, 1)}:h={max(y1 - y0, 1)},"
        f"crop={cover.w}:{cover.h}:{cover.x}:{cover.y},boxblur={blur}:2,format=yuva420p[bl]",
        "[1:v]format=gray[m]", "[bl][m]alphamerge[patch]",
        f"[base][patch]overlay={cover.x}:{cover.y}:eof_action=pass{when}[cov]",
    ]


def _frame_size(video: Path) -> tuple[int, int]:
    info = probe(video)
    return info.width, info.height


def _enable(lines: list[TimedLine]) -> str:
    return "+".join(f"between(t,{x.start:.3f},{x.end:.3f})" for x in lines) or "0"


def _filter_path(p: Path) -> str:
    """Escape đường dẫn cho filter ass= (Windows có ':' và '\\')."""
    s = p.resolve().as_posix()
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def render(video: Path, ass: Path, out: Path, duration: float, cover: Box | None, captions: list[TimedLine],
           audio: Path | None, keep_original_audio: bool, workdir: Path, size: tuple[int, int] | None = None,
           clean: tuple[Path, float] | None = None) -> Path:
    """Xuất MP4 H.264/AAC. Thời lượng luôn = video gốc.

    `clean`: clip đã xoá riêng nét chữ cũ (giữ glow) — dán đúng chỗ, không làm mờ gì thêm.
    """
    args = ["-i", str(video)]
    parts: list[str] = []
    last = "0:v"
    if cover and captions and clean:
        args += ["-itsoffset", f"{clean[1]:.3f}", "-i", str(clean[0])]
        parts.append(f"[0:v][1:v]overlay={cover.x}:{cover.y}:eof_action=pass:enable='{_enable(captions)}'[cov]")
        last = "cov"
    elif cover and captions:
        mask = feather_mask(cover, workdir / "mask.png")
        args += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(mask)]
        w, h = size or _frame_size(video)
        parts += _cover_parts(cover, w, h, _enable(captions))
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


def preview_frame(video: Path, t: float, ass: Path, cover: Box | None, out: Path, workdir: Path,
                  size: tuple[int, int] | None = None, clean: tuple[Path, float] | None = None) -> Path:
    """Ảnh xem trước 1 khung hình với caption mới (ass phải có câu chạy từ 0s) — để chỉnh vị trí/kiểu chữ nhanh."""
    args = ["-ss", f"{max(t, 0):.3f}", "-i", str(video)]
    parts: list[str] = []
    last = "0:v"
    if cover and clean and t >= clean[1]:
        args += ["-ss", f"{t - clean[1]:.3f}", "-i", str(clean[0])]
        parts.append(f"[0:v][1:v]overlay={cover.x}:{cover.y}:eof_action=pass[cov]")
        last = "cov"
    elif cover:
        mask = feather_mask(cover, workdir / "mask.png")
        args += ["-i", str(mask)]
        w, h = size or _frame_size(video)
        parts += _cover_parts(cover, w, h, None)
        last = "cov"
    parts.append(f"[{last}]ass=filename='{_filter_path(ass)}':fontsdir='{_filter_path(fonts_dir())}'[vout]")
    ffmpeg(*args, "-filter_complex", ";".join(parts), "-map", "[vout]", "-frames:v", "1", "-q:v", "3", str(out),
           timeout=60)
    return out
