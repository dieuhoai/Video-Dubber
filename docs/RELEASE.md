# Quy trình release

## Checklist trước khi tag
- [ ] `main` sạch, CI `test` xanh trên cả 3 OS.
- [ ] `python scripts/check_privacy.py --all` sạch.
- [ ] `CHANGELOG.md` mục `[Unreleased]` đã ghi đủ thay đổi người dùng thấy được.
- [ ] Build thử local: `pyinstaller build/app.spec --noconfirm --workpath build/out --distpath dist` rồi chạy exe.

## Phát hành
```bash
python scripts/bump_version.py patch      # hoặc minor / major / X.Y.Z
git add -A
git commit -m "chore(release): vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```
Workflow `release.yml` sẽ: kiểm tag khớp version → test → đóng gói → smoke test exe → đính kèm
`VideoDubber-windows.zip` và `VideoDubber-macos.zip` vào GitHub Release.

## Sau release
- Tải zip từ trang Release về một máy sạch, mở thử.
- Nếu lỗi: **không xoá tag đã công bố**; sửa và phát hành bản patch.

## Lần đầu công khai repo
- Squash lịch sử nếu commit cũ từng chứa đường dẫn máy/dữ liệu khách.
- Bật *Settings → Template repository* nếu đây là repo template.
- Ký mã (tuỳ chọn): Windows Authenticode, macOS notarization — thêm secrets vào workflow khi có chứng chỉ.

## SemVer
- `MAJOR`: đổi định dạng preset/file mà bản cũ không đọc được.
- `MINOR`: tính năng mới, tương thích ngược.
- `PATCH`: sửa lỗi.
