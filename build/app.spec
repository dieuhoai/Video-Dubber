# PyInstaller spec — bản onedir cho Windows (.exe) và macOS (.app).
#   pyinstaller build/app.spec --noconfirm --workpath build/out --distpath dist
# Tool ngoài (nếu có) đặt trong bin/ — tải bằng script trong scripts/ trước khi build.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).parent
APP = "VideoDubber"            # đổi bởi scripts/new_project.py
BUNDLE_ID = "io.github.videodubber"

datas = [
    (str(ROOT / "web" / "static"), "web/static"),
    (str(ROOT / "fonts"), "fonts"),
    (str(ROOT / "build" / "fonts.conf"), "."),
    *[(str(p), "models") for p in (ROOT / "models").glob("*") if p.is_file() and p.name != ".gitkeep"],
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "LICENSE"), "."),
]
binaries = [(str(p), "bin") for p in (ROOT / "bin").glob("*")
            if p.is_file() and p.name not in (".gitkeep", "uv", "uv.exe")]  # uv chỉ dùng lúc cài, không cần trong app

hidden = ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
          "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.websockets_impl",
          "uvicorn.lifespan.on", "multipart", "kokoro_onnx", "onnxruntime",
          "soundfile", "edge_tts"]

# Thư viện giọng đọc/tách nhạc có file dữ liệu + thư viện động riêng → gom đủ, thiếu là lỗi lúc chạy.
for pkg in ("kokoro_onnx", "espeakng_loader", "phonemizer", "language_tags", "segments", "csvw", "onnxruntime",
            "soundfile", "edge_tts"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:  # noqa: BLE001 — gói không có trên máy build thì bỏ qua
        continue
    datas += d
    binaries += b
    hidden += h
for dist in ("kokoro-onnx", "espeakng-loader", "phonemizer", "phonemizer-fork", "onnxruntime", "edge-tts"):
    try:
        datas += copy_metadata(dist)
    except Exception:  # noqa: BLE001
        pass

a = Analysis([str(ROOT / "build" / "launcher.py")], pathex=[str(ROOT)], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["pytest", "playwright"], noarchive=False)
pyz = PYZ(a.pure)
icon = ROOT / "build" / ("icon.ico" if sys.platform == "win32" else "icon.icns")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP, console=True,
          icon=str(icon) if icon.exists() else None, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
if sys.platform == "darwin":
    app = BUNDLE(coll, name=f"{APP}.app", icon=str(icon) if icon.exists() else None, bundle_identifier=BUNDLE_ID)
