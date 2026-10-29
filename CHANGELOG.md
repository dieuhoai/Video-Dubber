# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/).

## [Unreleased]

### Sửa
- Xuất video nhanh hơn: mã hoá H.264 dùng preset `veryfast` (trước là `medium`), chất lượng crf 18 giữ nguyên, file nhỏ hơn; khoảng 2 lần nhanh hơn.
- Giọng đọc được lưu đệm: cùng câu + ngôn ngữ + giọng chỉ tạo một lần, lần sau (render lại, video trùng câu) lấy ngay từ bộ nhớ đệm.

## [0.1.7] - 2026-10-28
### Sửa
- Tự cập nhật trên Windows: luôn chép đè đủ file mới (trước đây robocopy có thể bỏ qua file trùng kích thước + thời gian); đường dẫn có dấu tiếng Việt, ngoặc hoặc dấu % không còn làm hỏng bước thay file.

## [0.1.6] - 2026-10-28
### Thêm
- Tự cập nhật ngay trong tool: khi có bản mới trên GitHub, đầu trang hiện "Có bản mới — Cập nhật ngay". Bấm một lần, tool tự tải, cài đè (app Windows, app Mac hoặc chạy từ mã nguồn) rồi tự mở lại đúng trang đang dùng; video và phần đang làm dở giữ nguyên. Không cập nhật khi đang xuất video. Máy chủ dùng chung có thể tắt bằng `VIDEODUBBER_NO_UPDATE=1`.
### Sửa
- Lỗi "Thiếu thư viện tách nhạc" khi chạy từ mã nguồn bằng môi trường cũ: tool phát hiện ngay ở bước 1; nút "Cài & tải đủ để tách nhạc" tự cài thư viện còn thiếu (kể cả khi môi trường không có pip) rồi tải mô hình — không cần gõ lệnh, không cần mở lại tool.
- Hai chế độ "Tách nhạc, đọc voice mới" và "Tách nhạc + voice tải lên" bị khoá khi bản đang chạy thiếu mô hình AI (chạy từ mã nguồn, hoặc bản tự đóng gói không kèm mô hình). Nay có nút "Tải mô hình AI" ngay ở bước 1: tải ~420 MB một lần, có thanh tiến độ, xong tự mở khoá.

## [0.1.4] - 2026-10-28
### Thêm
- Tải nhiều video một lần ở bước 1: các video dùng chung chữ, kiểu chữ, ngôn ngữ, hook và bản dịch; bấm "Tạo video" một lần là xuất hết (mỗi video × ngôn ngữ × hook) vào chung 1 file ZIP, tên file có thêm tên video.
- Vị trí chữ và vùng che chỉnh riêng từng video, hoặc tick "Dùng cùng vị trí cho tất cả video".
- Kéo thả trên khung xem trước: khung xanh = chữ mới, khung đỏ = vùng che chữ cũ; kéo góc để đổi cỡ, phím mũi tên để chỉnh tinh.
- Không còn mất chữ đã nhập: tải video khác, đổi video, mở video cũ, tải lại trang hay mở lại tool đều giữ nguyên (tự lưu nháp). Chỉ nút Reset (có hỏi lại) mới xoá hết.
- Video mới khác độ phân giải tự co giãn vị trí/cỡ chữ và vùng che; câu dài hơn video được cắt và báo.
### Sửa
- Vùng che có kích thước số lẻ làm hỏng "Xem thử" và xuất video.
- Khung xem trước bị viền xám trên màn hình thấp làm vùng che lệch vị trí; ô "Tên gọi" bị đè chữ trên điện thoại.
- Xoá caption cũ kiểu mới "Chỉ xoá chữ, giữ nền glow": chỉ thay nét chữ cũ, nền glow và phần video xung quanh giữ nguyên — không còn dải mờ lớn che video. Kiểu cũ "Làm mờ cả khung" vẫn chọn được.
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
