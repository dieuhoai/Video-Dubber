"""Hook PreToolUse(Bash): chạy check_privacy trước `git commit` / `git push`; chặn nếu phát hiện dữ liệu nhạy cảm.

Claude Code gửi JSON qua stdin; exit 2 + stderr = chặn lệnh và báo lý do cho Claude.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except (ValueError, AttributeError):
        return 0
    if not re.search(r"\bgit\s+(?:-C\s+\S+\s+)?(commit|push)\b", cmd):
        return 0
    mode = ["--all"] if re.search(r"\bgit\s+(?:-C\s+\S+\s+)?push\b", cmd) else []
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_privacy.py"), *mode], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout)
        sys.stderr.write("\nĐã chặn lệnh git. Gỡ dữ liệu nhạy cảm khỏi stage rồi thử lại.\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main())
