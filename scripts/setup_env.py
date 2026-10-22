"""Chuẩn bị môi trường chạy bằng một lệnh: tạo .venv, cài thư viện, (tuỳ chọn) trình duyệt test UI.

Dùng: python scripts/setup_env.py [--ui]
Chạy lại nhiều lần không sao — bước nào xong rồi sẽ bỏ qua.
"""
from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True, timeout=1800)


def main(argv: list[str]) -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 — người dùng có thể chạy bằng Python cũ của hệ thống
        print("Cần Python 3.10 trở lên. Tải tại https://www.python.org/downloads/", file=sys.stderr)
        return 1
    if not venv_python().exists():
        print("→ Tạo môi trường .venv")
        venv.create(VENV, with_pip=True)
    py = str(venv_python())
    print("→ Cài thư viện (lần đầu mất vài phút)")
    run(py, "-m", "pip", "install", "-q", "--upgrade", "pip")
    run(py, "-m", "pip", "install", "-q", "-e", ".[dev]")
    if "--ui" in argv:
        print("→ Cài trình duyệt cho test giao diện")
        run(py, "-m", "playwright", "install", "chromium")
    print(f"✓ Môi trường sẵn sàng: {py}")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 — console cũ không hỗ trợ đổi encoding
            pass
    try:
        sys.exit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as e:
        print(f"Lỗi khi chạy: {' '.join(map(str, e.cmd))}\nKiểm tra kết nối mạng rồi chạy lại.", file=sys.stderr)
        sys.exit(1)
