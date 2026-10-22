"""Tăng phiên bản đồng bộ ở pyproject.toml + <pkg>/__init__.py và thêm mục CHANGELOG.

Dùng: python scripts/bump_version.py patch|minor|major|X.Y.Z
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def pkg_init() -> Path:
    m = re.search(r'include = \["(\w+)\*"', PYPROJECT.read_text(encoding="utf-8"))
    return ROOT / (m.group(1) if m else "videodubber") / "__init__.py"


def main(arg: str) -> int:
    text = PYPROJECT.read_text(encoding="utf-8")
    cur = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.M)
    if not cur:
        print("Không đọc được version trong pyproject.toml", file=sys.stderr)
        return 1
    ma, mi, pa = map(int, cur.groups())
    if arg == "major":
        new = f"{ma + 1}.0.0"
    elif arg == "minor":
        new = f"{ma}.{mi + 1}.0"
    elif arg == "patch":
        new = f"{ma}.{mi}.{pa + 1}"
    elif re.fullmatch(r"\d+\.\d+\.\d+", arg):
        new = arg
    else:
        print(__doc__, file=sys.stderr)
        return 2
    PYPROJECT.write_text(text.replace(cur.group(0), f'version = "{new}"', 1), encoding="utf-8")
    init = pkg_init()
    init.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new}"', init.read_text(encoding="utf-8")),
                    encoding="utf-8")
    plugin = ROOT / ".claude-plugin" / "plugin.json"  # chỉ có ở repo gốc (plugin lutech-tools)
    if plugin.exists():
        plugin.write_text(re.sub(r'"version": "[^"]+"', f'"version": "{new}"', plugin.read_text(encoding="utf-8"),
                                 count=1),
                          encoding="utf-8")
    cl = ROOT / "CHANGELOG.md"
    body = cl.read_text(encoding="utf-8")
    entry = f"## [{new}] - {dt.date.today().isoformat()}"
    if entry not in body:
        body = body.replace("## [Unreleased]", f"## [Unreleased]\n\n{entry}", 1)
        cl.write_text(body, encoding="utf-8")
    print(f"{ma}.{mi}.{pa} → {new}\nTiếp theo: kiểm CHANGELOG, commit, rồi `git tag v{new} && git push --tags`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
