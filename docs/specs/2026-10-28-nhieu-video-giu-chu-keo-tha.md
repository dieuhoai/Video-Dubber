# Spec: tải nhiều video, giữ chữ đã nhập, kéo thả vùng chữ

Ngày: 2026-10-28 · Người yêu cầu: Team Flyer

## Vấn đề
- Mỗi lần tải video mới, caption/lời thoại/kiểu chữ/bản dịch bị xoá, phải nhập lại.
- Chỉ tải và xuất được từng video một.
- Vị trí chữ mới và vùng che chữ cũ chỉ chỉnh bằng ô số.

## Tiêu chí chấp nhận (AC)
1. Tải video mới khi đang có template → video mới nhận caption, lời thoại, kiểu chữ, vùng che,
   cách xoá chữ, chế độ âm thanh (+ file nhạc/voice), glossary, app/concept. Khác độ phân giải →
   vị trí chữ, cỡ chữ, vùng che co giãn theo tỉ lệ. Câu bắt đầu sau khi video mới đã hết → bỏ và báo;
   câu kết thúc sau khi video hết → cắt cho vừa.
2. Bản dịch ở bước 3 không mất khi đổi video. Nút "Bắt đầu trống" xoá hết để làm từ đầu.
3. Chọn được nhiều file một lần; tải lần lượt, mỗi file có trạng thái (đang tải / xong / lỗi).
4. Các video tải chung thành một nhóm: chữ, kiểu chữ, âm thanh dùng chung; vị trí chữ + vùng che
   riêng từng video, trừ khi tick "Dùng cùng vị trí cho tất cả video" (co giãn theo tỉ lệ).
5. Bấm "Tạo video" một lần → xuất mọi video trong nhóm × mọi ngôn ngữ × mọi hook, chung 1 batch / 1 ZIP.
   Tên file có thêm tên video để không trùng.
6. Trên khung xem trước kéo được khung chữ mới (di chuyển; kéo góc = đổi bề rộng dòng) và vùng che
   chữ cũ (di chuyển; kéo góc = đổi cỡ). Ô số cập nhật theo.

## Không đổi
- Cách render, xoá chữ cũ, QA. Batch 1 video vẫn đặt tên file như cũ.
