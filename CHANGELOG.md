# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/).

## [Unreleased]
### Thêm
- Chế độ âm thanh "Tách nhạc + voice tải lên": tải file voice của bạn (MP3/WAV/M4A), tool bỏ giọng gốc, giữ nhạc nền đã tách, đặt voice từ giây bạn chọn; voice dài hơn video thì báo đỏ.
### Sửa
- Kiểm tra "Glossary" so khớp nguyên từ (trước đây chữ "ai" trong "maintenant" bị tính là "AI").
- Màn hình Kết quả ghi rõ tool đang làm bước nào (tách nhạc, tạo giọng câu 2/4, xuất video…); có link "Xem nhật ký" để gửi khi bị lỗi/kẹt (bản Mac chạy ngầm, không có cửa sổ đen).
- Video mới tải lên có sẵn 1 dòng caption để điền; nút Tiếp tục bị khoá thì có dòng giải thích cần làm gì.
- Caption mới ngắn hơn caption gốc không còn lộ chữ cũ ở 2 bên: vùng chữ cũ được xoá sạch (tô lại từ nền xung quanh) thay vì chỉ làm mờ.
### Thêm
- Tải video gốc, khai báo caption/lời thoại, xem thử caption mới trên khung hình.
- Nhân bản hàng loạt: mỗi dòng câu hook × mỗi ngôn ngữ = 1 video; 19 ngôn ngữ, giọng nữ/nam.
- Tách nhạc nền khỏi giọng gốc (chạy trên máy, không cần GPU); giọng đọc offline Kokoro + Microsoft Edge TTS.
- Kiểm tra tự động: thời lượng, tốc độ voice, chữ vừa khung, font đủ chữ, âm lượng −14 LUFS, glossary.
- Chế độ máy chủ nội bộ dùng chung (--host/--allow-host), tải ZIP kết quả.

### Added
- Plugin Claude Code `lutech-tools` (cài bằng `install.sh`): lệnh `/lutech-tools:new-tool`, `help` và các skill quy trình; hướng dẫn `docs/PLUGIN.md`.
- Chế độ cho người không biết code: lệnh `/lutech-tools:make-tool`, `fix-tool`, `package-tool`; 7 công thức tool UA có sẵn;
  cài bằng double-click (`install.bat`, `install.command`), chạy được cả khi chỉ có Claude Desktop (không cần CLI); hướng dẫn `docs/HUONG-DAN.md`.
- `scripts/setup_env.py` (chuẩn bị môi trường 1 lệnh) và `scripts/build_exe.py` (đóng gói zip 1 lệnh).

## [0.1.0] - 2026-10-04
### Added
- Khung dự án: lõi `videodubber`, CLI, Web UI local (FastAPI + Alpine.js), đóng gói PyInstaller, CI test + release.
