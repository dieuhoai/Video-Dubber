# Video Dubber — hướng dẫn cho Claude

Công cụ desktop chạy local: lõi Python `videodubber/` + CLI + Web UI (`web/`, FastAPI + Alpine.js),
đóng gói PyInstaller thành .exe/.app, phát hành qua GitHub Releases.

## Lệnh
```bash
.venv/Scripts/python -m pytest -q                 # toàn bộ test (unit + web + ui)
.venv/Scripts/python -m pytest -q -m "not ui"     # bỏ test trình duyệt
.venv/Scripts/ruff check .                         # lint
.venv/Scripts/python -m web.server --no-browser --port 8765 --token devtoken   # chạy UI dev
.venv/Scripts/python -m videodubber run <in> <out>   # CLI
python scripts/check_privacy.py                    # quét dữ liệu nhạy cảm trong file đã stage
python scripts/bump_version.py patch               # tăng version + CHANGELOG
```
(macOS/Linux: `.venv/bin/...`)

## Quy trình bắt buộc
Theo [docs/LIFECYCLE.md](docs/LIFECYCLE.md). Ứng với từng giai đoạn dùng skill của plugin **lutech-tools** (`skills/`, cài bằng `./install.sh`, xem [docs/PLUGIN.md](docs/PLUGIN.md)):
`/lutech-tools:new-tool` → `spec-feature` → `plan-feature` → `implement-tdd` → `review-change` (+ `ui-review` nếu đổi UI) → `qa-check` → `release`.
Không bỏ giai đoạn khi người dùng chưa đồng ý bỏ.

## Rule
Chi tiết trong `.claude/rules/` (tự nạp theo đường dẫn file):
- `architecture.md` — ranh giới lõi/web/CLI, nơi đặt code.
- `python.md` — style, lỗi, IO, encoding.
- `testing.md` — TDD, fixture, marker.
- `web-ui.md` — Alpine, CSP, i18n, a11y, responsive, design token.
- `security-privacy.md` — server local, dữ liệu khách, bí mật.
- `git-release.md` — commit, branch, version, release.

## Không bao giờ
- Commit dữ liệu khách, media, đường dẫn máy cá nhân, token (hook `.claude/hooks/guard_git.py` chặn `git commit`/`push`).
- Import `web` từ `videodubber`.
- Tải asset từ CDN lúc chạy; thêm inline `<script>`.
- Tạo repo GitHub, push, tag hoặc publish release khi người dùng chưa đồng ý rõ ràng.
- Báo "xong" khi chưa chạy test và thấy kết quả.
