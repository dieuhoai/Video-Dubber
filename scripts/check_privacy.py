"""Chặn dữ liệu khách hàng / bí mật / đường dẫn máy cá nhân lọt vào git.

Dùng: python scripts/check_privacy.py            # quét file đã stage
      python scripts/check_privacy.py --all      # quét mọi file đang được git theo dõi
Từ khoá riêng của dự án (tên app khách, tên công ty…) đặt trong `.privacy-blocklist` (KHÔNG commit file này;
mỗi dòng 1 từ khoá, không phân biệt hoa thường).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 5 * 1024 * 1024
BLOCKED_EXT = {".mp4", ".mov", ".mkv", ".mp3", ".wav", ".m4a", ".psd", ".xlsx", ".csv", ".env", ".pem", ".key",
               ".p12", ".keystore", ".jks"}
PATTERNS = {
    "đường dẫn máy cá nhân": re.compile(
        r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s\"']+|/Users/[a-z][\w.-]+/|/home/[a-z][\w.-]+/"),
    "khoá bí mật": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "token/API key": re.compile(
        r"(?i)\b(?:ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})"),
}
SKIP = {"scripts/check_privacy.py"}


def git_files(all_files: bool) -> list[str]:
    args = ["git", "ls-files"] if all_files else ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [f for f in out.splitlines() if f]


def blocklist() -> list[str]:
    p = ROOT / ".privacy-blocklist"
    if not p.exists():
        return []
    lines = (w.strip() for w in p.read_text(encoding="utf-8").splitlines())
    return [w.lower() for w in lines if w and not w.startswith("#")]


def main(argv: list[str]) -> int:
    words = blocklist()
    problems: list[str] = []
    for rel in git_files("--all" in argv):
        if rel in SKIP:
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in BLOCKED_EXT:
            problems.append(f"{rel}: loại file bị cấm commit ({path.suffix})")
            continue
        if path.stat().st_size > MAX_BYTES:
            problems.append(f"{rel}: file > {MAX_BYTES // 1024 // 1024}MB")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, rx in PATTERNS.items():
            m = rx.search(text)
            if m:
                problems.append(f"{rel}: {label}: {m.group(0)[:60]!r}")
        low = text.lower()
        problems += [f"{rel}: từ khoá riêng tư '{w}'" for w in words if w in low]
    if problems:
        print("✗ Kiểm tra quyền riêng tư thất bại:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    print("✓ Không thấy dữ liệu nhạy cảm")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main(sys.argv[1:]))
