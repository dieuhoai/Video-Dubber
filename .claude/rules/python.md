---
paths:
  - "**/*.py"
---
# Python

- Python ≥ 3.10, `from __future__ import annotations`, type hint cho hàm public. Ruff (line 120) phải sạch.
- Đọc/ghi text luôn `encoding="utf-8"`; ghi file kết quả/cấu hình qua `io_utils.atomic_write_text` / `write_json`.
- Dùng `pathlib.Path`, không nối chuỗi đường dẫn. Phải chạy được với tên file có dấu tiếng Việt, khoảng trắng, emoji, dấu nháy.
- Bắt exception cụ thể. `except Exception` chỉ ở ranh giới (mỗi item của batch, worker thread) và phải kèm `# noqa: BLE001 — lý do`.
- Lỗi một item không làm dừng batch; gom vào `ItemResult(ok=False, error=...)`.
- Thông báo lỗi cho người dùng bằng tiếng Việt, nói rõ cần làm gì. Docstring/comment ngắn, tiếng Việt, giải thích *vì sao*.
- Không thêm dependency khi thư viện chuẩn làm được; thêm thì ghi vào `pyproject.toml` và nêu lý do trong PR.
