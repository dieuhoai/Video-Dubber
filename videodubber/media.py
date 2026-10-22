"""Gọi ffmpeg/ffprobe. Tìm trong `bin/` của tool trước (bản đóng gói), rồi PATH."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .defaults import resource_root


class MediaError(RuntimeError):
    """Lỗi xử lý media — thông điệp đã là câu người dùng đọc được."""


def find_tool(name: str) -> str:
    for cand in (resource_root() / "bin" / f"{name}.exe", resource_root() / "bin" / name):
        if cand.is_file():
            return str(cand)
    found = shutil.which(name)
    if not found:
        raise MediaError(f"Không tìm thấy {name}. Cài FFmpeg (https://ffmpeg.org) hoặc chép {name} vào thư mục bin/.")
    return found


def _env() -> dict[str, str]:
    """ffmpeg tĩnh trên Windows/macOS không biết font hệ thống ở đâu → chỉ cho nó qua FONTCONFIG_FILE."""
    env = dict(os.environ)
    if "FONTCONFIG_FILE" not in env and sys.platform in ("win32", "darwin"):
        name = "fonts-win.conf" if sys.platform == "win32" else "fonts-mac.conf"
        for cand in (resource_root() / name, resource_root() / "build" / name):
            if cand.is_file():
                env["FONTCONFIG_FILE"] = str(cand)
                break
    return env


def run(args: list[str], timeout: float = 900) -> subprocess.CompletedProcess:
    """Chạy tool ngoài; lỗi → MediaError kèm vài dòng cuối của stderr để dễ tra."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           env=_env())
    except subprocess.TimeoutExpired as e:
        raise MediaError(f"{Path(args[0]).name} chạy quá {timeout:.0f}s và đã bị dừng") from e
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-6:])
        raise MediaError(f"{Path(args[0]).name} báo lỗi:\n{tail}")
    return p


def ffmpeg(*args: str, timeout: float = 900) -> subprocess.CompletedProcess:
    return run([find_tool("ffmpeg"), "-hide_banner", "-nostdin", "-y", *args], timeout=timeout)


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool


def probe(path: Path) -> VideoInfo:
    p = run([find_tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], 60)
    data = json.loads(p.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        raise MediaError(f"“{Path(path).name}” không có hình — hãy chọn file video (MP4/MOV).")
    num, _, den = str(v.get("r_frame_rate", "30/1")).partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    dur = float(v.get("duration") or data.get("format", {}).get("duration") or 0)
    if dur <= 0:
        raise MediaError(f"Không đọc được thời lượng của “{Path(path).name}”.")
    return VideoInfo(int(v["width"]), int(v["height"]), dur, fps,
                     any(s.get("codec_type") == "audio" for s in streams))


def audio_duration(path: Path) -> float:
    p = run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], 60)
    try:
        return float(p.stdout.strip())
    except ValueError as e:
        raise MediaError(f"Không đọc được độ dài âm thanh “{Path(path).name}”.") from e


def loudness(path: Path) -> float | None:
    """Integrated loudness (LUFS) theo EBU R128; None nếu file không có tiếng."""
    p = run([find_tool("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:a:0?", "-af", "ebur128",
             "-f", "null", "-"], 300)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    return float(m[-1]) if m else None


def extract_frame(video: Path, t: float, out: Path, width: int = 0) -> Path:
    vf = ["-vf", f"scale={width}:-2"] if width else []
    ffmpeg("-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1", *vf, "-q:v", "3", str(out), timeout=60)
    return out
