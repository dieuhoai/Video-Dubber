# ADR-0001: Giao diện = web server local + trình duyệt, đóng gói bằng PyInstaller

- Ngày: 2026-10-04 · Trạng thái: Chấp nhận

## Bối cảnh
Tool cho người dùng không rành kỹ thuật, chạy trên Windows và macOS, xử lý file nặng trên máy.

## Các lựa chọn đã cân nhắc
- Electron/Tauri: đẹp nhưng thêm toolchain JS/Rust, file lớn.
- Tkinter/Qt: một ngôn ngữ nhưng UI khó làm đẹp, Qt nặng.
- **FastAPI local + Alpine.js trong trình duyệt mặc định**: một ngôn ngữ cho lõi, UI web hiện đại, không build step JS.

## Quyết định
Chọn FastAPI + Alpine.js, chỉ nghe 127.0.0.1 với token mỗi phiên; PyInstaller onedir cho .exe/.app.

## Hệ quả
- Phải giữ bảo mật server local (token, Host/Origin, CSP) — có test trong `tests/web/test_api.py`.
- Asset front-end vendored trong `web/static/vendor`, không CDN.
- App chưa ký sẽ bị SmartScreen/Gatekeeper cảnh báo — hướng dẫn trong README.
