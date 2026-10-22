"""Đường dẫn & hằng số dùng chung. Test monkeypatch các biến này sang tmp_path."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_SLUG = "videodubber"


def _user_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_SLUG


USER_DIR = _user_dir()
SETTINGS_FILE = USER_DIR / "settings.json"
USER_PRESET_DIR = USER_DIR / "presets"


def resource_root() -> Path:
    """Gốc tài nguyên: thư mục repo khi chạy source, sys._MEIPASS khi chạy bản PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


BUILTIN_PRESET_DIR = resource_root() / "presets"
