---
paths:
  - "tests/**"
  - "videodubber/**"
  - "web/**"
---
# Test

- TDD: viết test → chạy thấy **đỏ đúng lý do** → code tối thiểu cho xanh → dọn. Bug fix bắt đầu bằng test tái hiện.
- Mỗi tiêu chí chấp nhận (AC) trong spec có ít nhất 1 test; tên test mô tả hành vi.
- Vị trí: `tests/unit/` (lõi, nhanh), `tests/web/` (API qua `TestClient`, kèm token), `tests/ui/` (Playwright, marker `ui`).
- Dữ liệu test tự sinh trong `tmp_path` (fixture `sample_input`) — luôn có edge case: tên có dấu/nháy, file hỏng, thư mục con.
- Fixture autouse `isolated_user_dir` đã chuyển thư mục cấu hình sang tmp — không bao giờ ghi vào máy thật.
- Dữ liệu thật của khách: marker `real`, đọc đường dẫn từ biến `VIDEODUBBER_REAL_DATA`, không copy vào repo.
- UI test: kiểm cả 375px và 1440px, không lỗi JS (`pageerror`), không tràn ngang.
- Không `sleep` cố định để chờ; poll có timeout.
