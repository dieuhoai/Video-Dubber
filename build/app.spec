# PyInstaller spec — bản onedir cho Windows (.exe) và macOS (.app).
#   pyinstaller build/app.spec --noconfirm --workpath build/out --distpath dist
# Tool ngoài (nếu có) đặt trong bin/ — tải bằng script trong scripts/ trước khi build.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
APP = "VideoDubber"            # đổi bởi scripts/new_project.py
BUNDLE_ID = "io.github.videodubber"

datas = [
    (str(ROOT / "web" / "static"), "web/static"),
    (str(ROOT / "fonts"), "fonts"),
    *[(str(p), "models") for p in (ROOT / "models").glob("*") if p.is_file() and p.name != ".gitkeep"],
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "LICENSE"), "."),
]
binaries = [(str(p), "bin") for p in (ROOT / "bin").glob("*") if p.is_file() and p.name != ".gitkeep"]

hidden = ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
          "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.websockets_impl",
          "uvicorn.lifespan.on", "multipart", "kokoro_onnx", "onnxruntime",
          "soundfile", "edge_tts"]

a = Analysis([str(ROOT / "build" / "launcher.py")], pathex=[str(ROOT)], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["pytest", "playwright"], noarchive=False)
pyz = PYZ(a.pure)
icon = ROOT / "build" / ("icon.ico" if sys.platform == "win32" else "icon.icns")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP, console=True,
          icon=str(icon) if icon.exists() else None, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
if sys.platform == "darwin":
    app = BUNDLE(coll, name=f"{APP}.app", icon=str(icon) if icon.exists() else None, bundle_identifier=BUNDLE_ID)
