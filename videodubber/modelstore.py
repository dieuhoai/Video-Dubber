"""Mô hình AI (tách nhạc, giọng đọc offline): tìm ở đâu, thiếu thì tự tải.

Thứ tự tìm: VIDEODUBBER_MODELS → thư mục models/ cạnh app (bản đóng gói đã kèm sẵn) → USER_DIR/models (nơi tool tự
tải về khi chạy từ mã nguồn hoặc bản đóng gói thiếu mô hình). Không có mô hình thì các chế độ "tách nhạc" bị khoá —
trước đây người dùng không biết cách mở khoá, nay có nút tải ngay trên giao diện.
"""
from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from pathlib import Path

from . import defaults as D

SEPARATION = "UVR-MDX-NET-Inst_HQ_3.onnx"
KOKORO_MODEL = "kokoro-v1.0.onnx"
KOKORO_VOICES = "voices-v1.0.bin"
FILES: dict[str, str] = {
    SEPARATION: "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/" + SEPARATION,
    KOKORO_MODEL: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/" + KOKORO_MODEL,
    KOKORO_VOICES: "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/" + KOKORO_VOICES,
}
Progress = Callable[[str, int, int], None]


def search_dirs() -> list[Path]:
    dirs = []
    if os.environ.get("VIDEODUBBER_MODELS"):
        dirs.append(Path(os.environ["VIDEODUBBER_MODELS"]))
    dirs += [D.resource_root() / "models", D.USER_DIR / "models"]
    return dirs


def find_model(name: str) -> Path | None:
    for d in search_dirs():
        p = d / name
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def missing() -> list[str]:
    return [n for n in FILES if find_model(n) is None]


def download_all(on_progress: Progress | None = None) -> None:
    """Tải mô hình còn thiếu vào USER_DIR/models.

    Ghi file tạm rồi đổi tên: mất mạng giữa chừng không để lại file hỏng.
    """
    dest = D.USER_DIR / "models"
    dest.mkdir(parents=True, exist_ok=True)
    for name in missing():
        tmp = dest / f"{name}.part"
        try:
            with urllib.request.urlopen(FILES[name], timeout=60) as r, tmp.open("wb") as w:  # noqa: S310 — URL cố định
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while chunk := r.read(1024 * 1024):
                    w.write(chunk)
                    done += len(chunk)
                    if on_progress:
                        on_progress(name, done, total)
            tmp.replace(dest / name)
        finally:
            tmp.unlink(missing_ok=True)
