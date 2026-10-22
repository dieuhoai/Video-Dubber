"""Đóng gói app thành file zip gửi được cho người khác (Windows .exe / macOS .app).

Dùng: python scripts/build_exe.py
Kết quả: dist/<App>-<windows|macos|linux>.zip
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from setup_env import venv_python  # noqa: E402


def app_name() -> str:
    m = re.search(r'^APP = "([^"]+)"', (ROOT / "build" / "app.spec").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "App"


def main() -> int:
    py = venv_python()
    if not py.exists():
        print("Chưa có môi trường. Chạy trước: python scripts/setup_env.py", file=sys.stderr)
        return 1
    subprocess.run([str(py), "-m", "pip", "install", "-q", "pyinstaller"], cwd=ROOT, check=True, timeout=900)
    subprocess.run([str(py), "-m", "PyInstaller", "build/app.spec", "--noconfirm", "--workpath", "build/out",
                    "--distpath", "dist"], cwd=ROOT, check=True, timeout=1800)
    app = app_name()
    osname = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    src = ROOT / "dist" / (f"{app}.app" if osname == "macos" else app)
    archive = shutil.make_archive(str(ROOT / "dist" / f"{app}-{osname}"), "zip", src.parent, src.name)
    print(f"✓ Đã đóng gói: {archive}\nGửi file zip này cho người dùng — giải nén rồi mở {app}.")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 — console cũ không hỗ trợ đổi encoding
            pass
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f"Đóng gói thất bại ở: {' '.join(map(str, e.cmd))}", file=sys.stderr)
        sys.exit(1)
