"""Nghiệp vụ mẫu: quét file theo preset, thống kê dòng/từ, ghi kết quả.

Thay phần này bằng nghiệp vụ thật nhưng giữ nguyên các nguyên tắc:
- hàm thuần, nhận model, trả model — không print, không import web;
- lỗi của một item không làm dừng cả batch;
- báo tiến độ qua callback `on_progress(done, total, item)`;
- hỗ trợ huỷ qua `should_stop()`.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from .io_utils import atomic_write_text
from .models import ItemResult, JobRequest, JobResult, Preset

Progress = Callable[[int, int, ItemResult], None]


def scan(input_dir: Path, preset: Preset) -> list[Path]:
    root = Path(input_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Không phải thư mục: {root}")
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in preset.extensions)


def process_one(src: Path, input_dir: Path, output_dir: Path, preset: Preset) -> ItemResult:
    try:
        text = src.read_text(encoding="utf-8")
        out = Path(output_dir) / src.relative_to(input_dir)
        atomic_write_text(out, text.upper() if preset.uppercase else text)
        return ItemResult(source=src, output=out, ok=True, lines=len(text.splitlines()), words=len(text.split()))
    except Exception as e:  # noqa: BLE001 — lỗi 1 item không được làm hỏng batch
        return ItemResult(source=src, ok=False, error=f"{type(e).__name__}: {e}")


def run_job(
    req: JobRequest,
    on_progress: Progress | None = None,
    should_stop: Callable[[], bool] | None = None,
    files: Iterable[Path] | None = None,
) -> JobResult:
    if Path(req.output_dir).resolve() == Path(req.input_dir).resolve():
        raise ValueError("Thư mục output phải khác thư mục input")
    items = list(files) if files is not None else scan(req.input_dir, req.preset)
    results: list[ItemResult] = []
    for i, f in enumerate(items, 1):
        if should_stop and should_stop():
            break
        r = process_one(f, req.input_dir, req.output_dir, req.preset)
        results.append(r)
        if on_progress:
            on_progress(i, len(items), r)
    return JobResult(items=results)
