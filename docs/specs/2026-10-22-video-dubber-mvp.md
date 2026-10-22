# Spec: Video Dubber MVP (phase 1)

Nguồn: brief "Tool nhân bản video quảng cáo đa ngôn ngữ (text + voice)" (Claude Docs, 2026-10-22).

## Phiếu tool (đã chốt với người dùng)
- **Loại:** web nội bộ dùng chung (FastAPI + Alpine), chạy trên 1 máy chủ trong mạng công ty; vẫn chạy được trên máy cá nhân.
- **Đầu vào:** chỉ có MP4 đã xuất (không có master sạch). Có thể thêm file nhạc nền riêng.
- **Giọng đọc:** Kokoro (offline, miễn phí, chạy trên máy chủ) cho es/fr/en/it/pt-BR/ja/zh/hi; ngôn ngữ khác dùng Microsoft Edge TTS (miễn phí, cần mạng). Dự phòng: espeak-ng.
- **Dịch:** người dùng dán bản dịch (hoặc dán prompt sang Claude rồi dán kết quả); nếu máy chủ có `ANTHROPIC_API_KEY` thì có nút dịch tự động.

## Luồng 4 màn hình
1. **Template** — upload MP4 → tool đọc kích thước/thời lượng. Người dùng nhập các câu caption (thời gian + chữ), khung che caption cũ,
   kiểu chữ; nhập lời thoại (hoặc bấm tự tách nếu máy chủ có Whisper); chọn cách xử lý âm thanh.
2. **Batch** — tick ngôn ngữ, chọn giọng nữ/nam.
3. **Duyệt bản dịch** — bảng ngôn ngữ × câu; cảnh báo câu dài hơn bản gốc > 30%.
4. **Kết quả** — lưới video, huy hiệu QA, tải từng file / ZIP, render lại 1 ngôn ngữ.

## Xử lý mỗi ngôn ngữ
- Xoá caption cũ: delogo tô lại toàn bộ vùng khung từ điểm ảnh viền ngoài, làm mờ nhẹ, mép trên/dưới mờ dần — chỉ trong thời gian caption hiện.
- Caption mới: ASS/libass, font Fredoka Bold (OFL, đóng kèm) + fallback Noto; chữ trắng viền đen, glow xanh ngọc; tự xuống dòng,
  tự giảm cỡ chữ để không quá `max_lines` dòng.
- Âm thanh: `original` (giữ nguyên, chỉ đổi chữ) · `music_file` · `uploaded_voice` (tách nhạc + file voice người dùng tải lên, không tua nhanh) · `separate` (tách nhạc bằng MDX-Net ONNX, chạy CPU) · `none`.
  Có voice: TTS từng câu, khớp thời lượng bằng `atempo` 0,9–1,15×, đặt đúng mốc; nhạc ducking dưới voice; loudnorm −14 LUFS.
- Đầu ra: MP4 H.264/AAC, giữ đúng thời lượng & kích thước gốc. Tên `{app}_{concept}_{lang}_{voice}_{hook}_{ratio}_v{n}.mp4`.

## QA tự động (mỗi video)
Thời lượng = gốc (±1 frame) · voice không vượt 1,15× · caption ≤ max_lines và cỡ chữ ≥ 70% · không thiếu glyph ·
loudness −14 ±1 LUFS (khi trộn lại âm) · glossary (từ không dịch) còn nguyên.

## Ngoài phạm vi (phase 2)
Inpainting xoá chữ thật sạch, clone giọng, sửa chữ trong ảnh AI, đa tỉ lệ khung, đẩy lên ad account, STT kiểm ngược.

## Xong khi
1 video 14 s → 5 ngôn ngữ chạy không lỗi, tất cả QA xanh với bản dịch hợp lý; test tự động xanh.
