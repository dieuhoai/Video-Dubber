# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Plugin Claude Code `lutech-tools` (cài bằng `install.sh`): lệnh `/lutech-tools:new-tool`, `help` và các skill quy trình; hướng dẫn `docs/PLUGIN.md`.
- Chế độ cho người không biết code: lệnh `/lutech-tools:make-tool`, `fix-tool`, `package-tool`; 7 công thức tool UA có sẵn;
  cài bằng double-click (`install.bat`, `install.command`), chạy được cả khi chỉ có Claude Desktop (không cần CLI); hướng dẫn `docs/HUONG-DAN.md`.
- `scripts/setup_env.py` (chuẩn bị môi trường 1 lệnh) và `scripts/build_exe.py` (đóng gói zip 1 lệnh).

## [0.1.0] - 2026-10-04
### Added
- Khung dự án: lõi `videodubber`, CLI, Web UI local (FastAPI + Alpine.js), đóng gói PyInstaller, CI test + release.
