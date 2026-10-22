"""CLI.

  videodubber langs                              # danh sách ngôn ngữ + giọng
  videodubber new video.mp4 --name "Bday hook"   # tạo template, in ra mã
  videodubber show <mã>                          # in template (JSON) để sửa
  videodubber update <mã> template.json          # ghi đè template từ file đã sửa
  videodubber render batch.json                  # chạy batch (BatchRequest JSON)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__, store
from .langs import LANGS
from .media import MediaError
from .models import BatchRequest, Template
from .processor import run_batch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="videodubber", description="Video Dubber — dòng lệnh")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("langs", help="Liệt kê ngôn ngữ")
    n = sub.add_parser("new", help="Tạo template từ video")
    n.add_argument("video", type=Path)
    n.add_argument("--name", default="")
    s = sub.add_parser("show", help="In template")
    s.add_argument("id")
    u = sub.add_parser("update", help="Ghi template từ file JSON")
    u.add_argument("id")
    u.add_argument("file", type=Path)
    r = sub.add_parser("render", help="Chạy batch từ file JSON")
    r.add_argument("file", type=Path)
    a = ap.parse_args(argv)
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass

    try:
        if a.cmd == "langs":
            for code, lang in LANGS.items():
                print(f"{code:6} {lang.name:22} {lang.voice_f} / {lang.voice_m}{'  [offline]' if lang.kokoro else ''}")
        elif a.cmd == "new":
            tpl = store.create_template(a.video, a.name or a.video.stem)
            print(tpl.id)
        elif a.cmd == "show":
            print(json.dumps(store.load_template(a.id).model_dump(mode="json"), ensure_ascii=False, indent=2))
        elif a.cmd == "update":
            data = json.loads(a.file.read_text(encoding="utf-8"))
            store.save_template(Template.model_validate({**data, "id": a.id}))
            print("Đã lưu")
        elif a.cmd == "render":
            req = BatchRequest.model_validate_json(a.file.read_text(encoding="utf-8"))
            res = run_batch(req, on_progress=lambda d, t, it: print(
                f"[{d}/{t}] {'OK ' if it.ok else 'LỖI'} {it.lang} {it.output.name if it.output else it.error}"))
            print(f"Xong: {res.ok_count}/{len(res.items)} — thư mục {store.batch_dir(res.batch_id)}")
            for it in res.items:
                for c in it.checks:
                    if not c.ok:
                        print(f"  ! {it.lang} · {c.name}: {c.detail}")
            return 1 if res.failed else 0
    except (ValueError, ValidationError, FileNotFoundError, MediaError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
