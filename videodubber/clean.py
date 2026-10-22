"""Xoá chữ của caption cũ nhưng giữ nguyên nền glow của nó — dấu vết nhỏ nhất có thể.

Cách làm (chỉ cần numpy + ffmpeg):
1. Caption cũ là lớp phủ đứng yên, còn video phía sau chuyển động → điểm ảnh nào gần như không đổi suốt thời gian
   caption hiện là thuộc lớp phủ (chữ + glow).
2. Trong lớp phủ, nét chữ là màu trắng/sáng hoặc viền tối → đó là vùng cần xoá.
3. Tô lại nét chữ bằng màu glow xung quanh (normalized convolution, lặp từ mép vào giữa).
Kết quả là một clip nhỏ đúng bằng khung che, dán đè lên video trong lúc caption hiện. Phần còn lại không bị đụng tới.
Nếu video phía sau cũng đứng yên (không phân biệt được lớp phủ) → trả None để dùng cách cũ (làm mờ cả khung).
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .media import MediaError, find_tool
from .models import Box, TimedLine

STATIC_STD = 12.0  # độ lệch chuẩn (0–255) dưới mức này coi là "đứng yên"


def _box_blur(np, a, r: int):
    for ax in (0, 1):
        pad = [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)]
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
        n = a.shape[ax]
        a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(n), axis=ax)) / (2 * r + 1)
    return a


def _dilate(np, m, r: int):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def _read(video: Path, box: Box, start: float, dur: float):
    import numpy as np
    p = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-vf", f"crop={box.w}:{box.h}:{box.x}:{box.y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=600)
    if p.returncode != 0:
        raise MediaError("Không đọc được khung hình để xoá chữ cũ")
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, box.h, box.w, 3)


def text_mask(frames):
    """Mặt nạ nét chữ cũ (True = cần xoá) hoặc None nếu không tách được lớp phủ khỏi nền."""
    import numpy as np
    sample = frames[:: max(len(frames) // 40, 1)].astype(np.float32)
    if len(sample) < 3:
        return None
    static = sample.std(0).mean(-1) < STATIC_STD
    frac = static.mean()
    if frac < 0.02 or frac > 0.92:  # không có lớp phủ, hoặc nền cũng đứng yên → không phân biệt được
        return None
    avg = sample.mean(0)
    lum, red = avg.mean(-1), avg[..., 0]
    # Chữ trắng (đỏ cao, khác glow xanh ngọc) hoặc viền tối, nằm trong vùng đứng yên.
    text = static & ((red > 165) | (lum < 70))
    if text.mean() < 0.002:
        return None
    return _dilate(np, text, 3)


def _fill(np, frame, mask):
    out = frame.astype(np.float32)
    todo = mask.copy()
    for r in (6, 12, 24, 48):  # tô từ mép nét chữ vào trong
        w = (~todo).astype(np.float32)
        num = np.stack([_box_blur(np, out[..., c] * w, r) for c in range(3)], -1)
        den = _box_blur(np, w, r)[..., None]
        ok = (den[..., 0] > 0.05) & todo
        out[ok] = (num / np.maximum(den, 1e-6))[ok]
        todo &= ~ok
        if not todo.any():
            break
    smooth = np.stack([_box_blur(np, out[..., c], 3) for c in range(3)], -1)
    out[mask] = smooth[mask]
    return out.clip(0, 255).astype(np.uint8)


def cache_key(video: Path, box: Box, captions: list[TimedLine]) -> str:
    raw = f"{video.name}|{video.stat().st_size}|{box.model_dump_json()}|" + "|".join(
        f"{c.start:.3f}-{c.end:.3f}" for c in captions)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def clean_clip(video: Path, box: Box, captions: list[TimedLine], fps: float,
               cache_dir: Path) -> tuple[Path, float] | None:
    """Clip đã xoá chữ (đúng bằng khung che) + giây bắt đầu của nó; None → dùng cách làm mờ cả khung."""
    import numpy as np
    if not captions:
        return None
    start = max(min(c.start for c in captions) - 0.05, 0.0)
    end = max(c.end for c in captions) + 0.05
    out = cache_dir / f"clean_{cache_key(video, box, captions)}.mp4"
    if out.is_file():
        return out, start
    frames = _read(video, box, start, end - start)
    # Chỉ dò lớp phủ trong lúc chắc chắn caption đang hiện: khung hình ngay sau khi caption tắt (do mốc giây
    # nhập lệch một chút) làm điểm ảnh chữ "chuyển động" và lọt khỏi mặt nạ.
    core = [f for i, f in enumerate(frames) if any(c.start + 0.15 <= start + i / fps <= c.end - 0.25 for c in captions)]
    mask = text_mask(np.stack(core)) if len(core) >= 3 else text_mask(frames)
    if mask is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.mp4")
    enc = subprocess.Popen([find_tool("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{box.w}x{box.h}", "-r", f"{fps:.5f}", "-i", "-", "-c:v", "libx264", "-preset",
                            "veryfast", "-crf", "12", "-pix_fmt", "yuv444p", str(tmp)], stdin=subprocess.PIPE)
    try:
        for f in frames:
            enc.stdin.write(_fill(np, f, mask).tobytes())  # type: ignore[union-attr]
        enc.stdin.close()  # type: ignore[union-attr]
        if enc.wait(timeout=600) != 0:
            raise MediaError("Không ghi được clip đã xoá chữ")
    except BaseException:
        enc.kill()
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(out)
    return out, start
