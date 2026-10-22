# Bảo mật & quyền riêng tư

- Server chỉ bind `127.0.0.1`. Giữ nguyên guard: token mỗi phiên, kiểm `Host`/`Origin`, CSP, `X-Content-Type-Options`.
  Endpoint mới dưới `/api` tự được bảo vệ — không tạo route ngoài `/api` trả dữ liệu.
- Input đường dẫn từ UI: validate tồn tại/kiểu; tên do người dùng đặt (preset…) qua whitelist regex, chống `../`.
- Subprocess: list args, không `shell=True`, có timeout.
- **Dữ liệu khách**: spec gốc, file mẫu, tên app khách nằm **ngoài repo**. Từ khoá riêng ghi trong `.privacy-blocklist`
  (gitignored). `scripts/check_privacy.py` + hook `guard_git.py` chặn commit có media, bí mật, đường dẫn thư mục người dùng trên máy cá nhân.
- Không log nội dung file của người dùng; log chỉ tên file và lỗi.
- Không telemetry, không gọi mạng lúc chạy trừ khi spec yêu cầu và người dùng bật.
- Khi đụng server/IO/subprocess: chạy `/security-review` trước khi merge.
