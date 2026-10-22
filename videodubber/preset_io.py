"""Nạp/lưu preset: built-in (repo/presets) + của người dùng (USER_PRESET_DIR)."""
from __future__ import annotations

import re
from pathlib import Path

from . import defaults as D
from .io_utils import read_json, write_json
from .models import Preset

_SAFE = re.compile(r"^[\w\- ]{1,80}$", re.UNICODE)


def _check_name(name: str) -> str:
    if not _SAFE.match(name):
        raise ValueError(f"Tên preset không hợp lệ: {name!r}")
    return name


def list_presets() -> list[str]:
    names: set[str] = set()
    for d in (D.BUILTIN_PRESET_DIR, D.USER_PRESET_DIR):
        if Path(d).is_dir():
            names.update(p.stem for p in Path(d).glob("*.json"))
    return sorted(names)


def load_preset(name: str) -> Preset:
    _check_name(name)
    for d in (D.USER_PRESET_DIR, D.BUILTIN_PRESET_DIR):
        p = Path(d) / f"{name}.json"
        if p.is_file():
            return Preset.model_validate(read_json(p))
    raise FileNotFoundError(f"Không có preset {name!r}")


def save_preset(preset: Preset) -> Path:
    p = Path(D.USER_PRESET_DIR) / f"{_check_name(preset.name)}.json"
    write_json(p, preset.model_dump(mode="json"))
    return p
