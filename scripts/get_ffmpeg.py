"""Tải ffmpeg + ffprobe (bản có libass để vẽ caption) vào bin/ — dùng khi build app và trên máy chưa có FFmpeg.

  python scripts/get_ffmpeg.py
Windows x64: BtbN FFmpeg-Builds (GPL) · macOS Apple Silicon: ffmpeg-static (b6.0) · Linux: dùng ffmpeg của hệ thống.
"""
from __future__ import annotations

import gzip
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
WIN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
MAC = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/{tool}-darwin-arm64.gz"


def _get(url: str, out: Path) -> Path:
    print(f"Đang tải {url.rsplit('/', 1)[-1]}…", flush=True)
    urllib.request.urlretrieve(url, out)  # noqa: S310 — URL cố định, https
    return out


def main() -> int:
    BIN.mkdir(exist_ok=True)
    if sys.platform == "win32":
        if (BIN / "ffmpeg.exe").is_file() and (BIN / "ffprobe.exe").is_file():
            print("Đã có ffmpeg trong bin/")
            return 0
        with tempfile.TemporaryDirectory() as tmp:
            z = _get(WIN, Path(tmp) / "ff.zip")
            with zipfile.ZipFile(z) as zf:
                for name in zf.namelist():
                    base = name.rsplit("/", 1)[-1]
                    if base in ("ffmpeg.exe", "ffprobe.exe"):
                        with zf.open(name) as src, (BIN / base).open("wb") as dst:
                            shutil.copyfileobj(src, dst)
    elif sys.platform == "darwin":
        if platform.machine() != "arm64":
            print("Máy Mac chip Intel: cài FFmpeg bằng Homebrew (brew install ffmpeg).", file=sys.stderr)
            return 1
        for tool in ("ffmpeg", "ffprobe"):
            if (BIN / tool).is_file():
                continue
            with tempfile.TemporaryDirectory() as tmp:
                gz = _get(MAC.format(tool=tool), Path(tmp) / f"{tool}.gz")
                with gzip.open(gz) as src, (BIN / tool).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            (BIN / tool).chmod((BIN / tool).stat().st_mode | stat.S_IEXEC)
    else:
        if not shutil.which("ffmpeg"):
            print("Linux: cài FFmpeg bằng trình quản lý gói (vd: sudo apt install ffmpeg).", file=sys.stderr)
            return 1
        print("Dùng ffmpeg của hệ thống.")
        return 0
    print(f"Xong: {', '.join(p.name for p in sorted(BIN.iterdir()) if p.name.startswith('ff'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
