from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from videodubber.models import Preset
from videodubber.preset_io import list_presets, load_preset, save_preset

router = APIRouter(prefix="/api/presets")


@router.get("")
def get_presets() -> dict:
    return {"names": list_presets()}


@router.get("/{name}")
def get_preset(name: str) -> dict:
    try:
        return load_preset(name).model_dump(mode="json")
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e)) from e


@router.put("/{name}")
def put_preset(name: str, body: dict) -> dict:
    try:
        p = Preset.model_validate({**body, "name": name})
        save_preset(p)
    except (ValidationError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    return p.model_dump(mode="json")
