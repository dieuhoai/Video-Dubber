---
paths:
  - "videodubber/**"
  - "web/**"
---
# Kiến trúc

- `videodubber/` là lõi: thuần Python, **không import `web`, `fastapi`, `uvicorn`**, không `print` (trừ `__main__.py`).
  Hàm nhận pydantic model, trả pydantic model. Tiến độ báo qua callback, huỷ qua `should_stop()`.
- `videodubber/__main__.py` (CLI) và `web/` là vỏ mỏng: parse input → gọi lõi → hiển thị. Không có logic nghiệp vụ.
- Model mới → `videodubber/models.py` (tách file khi > ~400 dòng). Validate tại model, không rải kiểm tra khắp nơi.
- Đường dẫn cấu hình/tài nguyên chỉ lấy từ `videodubber/defaults.py` (`resource_root()` hỗ trợ PyInstaller).
- API mới: 1 router / 1 file trong `web/api/`, prefix `/api/<nhóm>`, đăng ký trong `create_app`.
  Lỗi người dùng → `HTTPException(422|404|409, thông_điệp_tiếng_người)`.
- Việc dài chạy trong thread nền (`web/api/jobs.py`), trạng thái qua `STATE.update_job()` → WebSocket. Không chặn event loop.
- Tool ngoài (ffmpeg…) đặt trong `bin/`, tìm qua `resource_root() / "bin"` trước, rồi `PATH`. Gọi subprocess bằng list, không `shell=True`.
