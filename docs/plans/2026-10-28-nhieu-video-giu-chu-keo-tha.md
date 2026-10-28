# Kế hoạch
1. `store.copy_settings(src_id, dst_id)` + test (AC1).
2. `POST /api/templates` nhận `copy_from` (AC1, AC3).
3. `BatchRequest.template_ids` + `run_batch` chạy nhiều template, tên file có tên video (AC5).
4. UI: input `multiple` + danh sách nhóm + đồng bộ chữ dùng chung + ô tick vị trí (AC2–4).
5. UI: kéo thả 2 khung bằng pointer events (AC6). i18n vi/en.
6. Test UI Playwright: tải 2 video 1 lần, chữ giữ nguyên, kéo khung, xuất 2 video.
