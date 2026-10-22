"""Model dữ liệu (pydantic). Mọi input từ CLI/Web đều đi qua đây để được validate."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SLUG = re.compile(r"^[A-Za-z0-9-]{1,40}$")
AudioMode = Literal["original", "music_file", "separate", "uploaded_voice", "none"]


class Box(BaseModel):
    """Vùng chữ nhật trên khung hình (pixel của video gốc)."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class CaptionStyle(BaseModel):
    font: str = "Fredoka"
    size: int = Field(54, ge=10, le=300)
    text_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline: float = Field(3, ge=0, le=20)
    glow: bool = True
    glow_color: str = "#20E0E8"
    uppercase: bool = True
    center_x: int = Field(360, ge=0)
    center_y: int = Field(922, ge=0)
    max_width: int = Field(680, gt=0)
    max_lines: int = Field(3, ge=1, le=6)

    @field_validator("text_color", "outline_color", "glow_color")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError("màu phải dạng #RRGGBB")
        return v.upper()


class TimedLine(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _order(self) -> TimedLine:
        if self.end <= self.start:
            raise ValueError("thời điểm kết thúc phải sau thời điểm bắt đầu")
        return self


class Template(BaseModel):
    """Một video win đã được "mổ xẻ": caption, lời thoại, vùng che, cách xử lý âm thanh."""

    id: str = Field(pattern=r"^[a-z0-9]{6,32}$")
    name: str = Field(min_length=1, max_length=120)
    app: str = "app"
    concept: str = "concept"
    video: str = "source.mp4"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration: float = Field(gt=0)
    fps: float = Field(30, gt=0)
    source_lang: str = "fr"
    captions: list[TimedLine] = Field(default_factory=list)
    cover: Box | None = None
    style: CaptionStyle = Field(default_factory=CaptionStyle)
    voice: list[TimedLine] = Field(default_factory=list)
    audio_mode: AudioMode = "original"
    music: str | None = None
    voice_file: str | None = None  # voice tự thu/tạo sẵn (chế độ uploaded_voice), dùng chung cho mọi video
    voice_offset: float = Field(0.2, ge=0)
    glossary: list[str] = Field(default_factory=list)

    @field_validator("app", "concept")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = re.sub(r"[^A-Za-z0-9-]+", "", v.strip()) or "x"
        return v[:40]

    @model_validator(mode="after")
    def _inside(self) -> Template:
        for line in [*self.captions, *self.voice]:
            if line.start >= self.duration:
                raise ValueError(f"câu “{line.text[:30]}” bắt đầu sau khi video đã hết ({self.duration:.1f}s)")
        if self.cover and (self.cover.x + self.cover.w > self.width or self.cover.y + self.cover.h > self.height):
            raise ValueError("khung che caption nằm ngoài khung hình")
        return self

    @property
    def uses_voice(self) -> bool:
        """Có dùng giọng đọc AI theo từng câu không (chế độ voice tải lên thì không)."""
        return self.audio_mode in ("separate", "music_file", "none") and bool(self.voice)


class LangVariant(BaseModel):
    """Bản dịch cho một ngôn ngữ: số câu phải khớp với template."""

    lang: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    gender: Literal["f", "m"] = "f"
    captions: list[str] = Field(default_factory=list)
    voice: list[str] = Field(default_factory=list)
    hook: str = "h1"

    @field_validator("hook")
    @classmethod
    def _hook(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("mã hook chỉ gồm chữ, số, gạch ngang")
        return v


class BatchRequest(BaseModel):
    template_id: str = Field(pattern=r"^[a-z0-9]{6,32}$")
    variants: list[LangVariant] = Field(min_length=1)
    version: int = Field(1, ge=1, le=999)
    ratio: Literal["9x16"] = "9x16"


class QACheck(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class ItemResult(BaseModel):
    lang: str
    output: Path | None = None
    ok: bool
    error: str | None = None
    checks: list[QACheck] = Field(default_factory=list)

    @property
    def qa_ok(self) -> bool:
        return self.ok and all(c.ok for c in self.checks)


class JobResult(BaseModel):
    batch_id: str = ""
    items: list[ItemResult]

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.ok)

    @property
    def failed(self) -> list[ItemResult]:
        return [i for i in self.items if not i.ok]
