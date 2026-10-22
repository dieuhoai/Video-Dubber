"""Tải mô hình AI (không nằm trong git vì nặng ~420 MB) vào thư mục models/.

  python scripts/get_models.py            # tải đủ: tách nhạc + giọng đọc offline
  python scripts/get_models.py --only sep  # chỉ mô hình tách nhạc (67 MB)
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    "sep": [("UVR-MDX-NET-Inst_HQ_3.onnx",
             "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Inst_HQ_3.onnx")],
    "tts": [("kokoro-v1.0.onnx",
             "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"),
            ("voices-v1.0.bin",
             "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin")],
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=sorted(MODELS))
    ap.add_argument("--dest", type=Path, default=ROOT / "models")
    a = ap.parse_args(argv)
    a.dest.mkdir(parents=True, exist_ok=True)
    for group, files in MODELS.items():
        if a.only and group != a.only:
            continue
        for name, url in files:
            out = a.dest / name
            if out.is_file() and out.stat().st_size > 1_000_000:
                print(f"Đã có {name}")
                continue
            print(f"Đang tải {name}…", flush=True)
            tmp = out.with_suffix(out.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)  # noqa: S310 — URL cố định, https
            tmp.replace(out)
    print(f"Xong. Mô hình nằm ở {a.dest}")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 — console cũ không đổi được encoding
            pass
    sys.exit(main())
