"""Model dữ liệu (pydantic). Mọi input từ CLI/Web đều đi qua đây để được validate."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Preset(BaseModel):
    """Cấu hình tái sử dụng được. Thay bằng các trường của tool thật."""

    name: str = Field(min_length=1, max_length=80)
    extensions: list[str] = Field(default_factory=lambda: [".txt"])
    uppercase: bool = False

    @field_validator("extensions")
    @classmethod
    def _norm_ext(cls, v: list[str]) -> list[str]:
        out = []
        for e in v:
            e = e.strip().lower()
            if e:
                out.append(e if e.startswith(".") else f".{e}")
        if not out:
            raise ValueError("cần ít nhất 1 phần mở rộng")
        return out


class JobRequest(BaseModel):
    input_dir: Path
    output_dir: Path
    preset: Preset


class ItemResult(BaseModel):
    source: Path
    output: Path | None = None
    ok: bool
    error: str | None = None
    lines: int = 0
    words: int = 0


class JobResult(BaseModel):
    items: list[ItemResult]

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.ok)

    @property
    def failed(self) -> list[ItemResult]:
        return [i for i in self.items if not i.ok]
