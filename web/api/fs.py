"""Hộp chọn thư mục gốc của OS (chạy process con để không khoá event loop)."""
from __future__ import annotations

import json
import subprocess
import sys

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/fs")


@router.post("/pick")
def pick(body: dict | None = None) -> dict:
    kind = (body or {}).get("kind", "dir")
    initial = (body or {}).get("initial", "")
    if kind not in ("dir", "file"):
        raise HTTPException(422, "kind phải là dir|file")
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--pick", kind, initial]
    else:
        cmd = [sys.executable, "-m", "web.picker", kind, initial]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600, check=True).stdout
        return json.loads(out.strip().splitlines()[-1])
    except (subprocess.SubprocessError, ValueError, IndexError) as e:
        raise HTTPException(500, f"Không mở được hộp chọn: {e}") from e
