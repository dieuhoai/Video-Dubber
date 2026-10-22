"""CLI: `videodubber run <input> <output> --preset default`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .models import JobRequest
from .preset_io import list_presets, load_preset
from .processor import run_job


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="videodubber", description="Video Dubber — dòng lệnh")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="Liệt kê preset")
    r = sub.add_parser("run", help="Chạy xử lý")
    r.add_argument("input", type=Path)
    r.add_argument("output", type=Path)
    r.add_argument("--preset", default="default")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass

    if a.cmd == "presets":
        print("\n".join(list_presets()))
        return 0
    try:
        req = JobRequest(input_dir=a.input, output_dir=a.output, preset=load_preset(a.preset))
        res = run_job(req, on_progress=lambda d, t, it: print(f"[{d}/{t}] {'OK' if it.ok else 'LỖI'} {it.source.name}"))
    except (ValueError, FileNotFoundError, NotADirectoryError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 2
    print(f"Xong: {res.ok_count}/{len(res.items)} thành công")
    for f in res.failed:
        print(f"  x {f.source}: {f.error}", file=sys.stderr)
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
