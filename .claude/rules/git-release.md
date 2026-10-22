# Git & release

- Conventional Commits: `feat|fix|docs|test|refactor|perf|build|ci|chore(scope): mô tả`. Một commit = một ý.
- Làm việc trên nhánh `feat/<tên>` / `fix/<tên>`, merge vào `main` qua PR. Không commit thẳng `main` khi đã có remote.
- Mỗi thay đổi người dùng thấy được → thêm dòng vào `CHANGELOG.md` mục `[Unreleased]`.
- Version chỉ đổi bằng `scripts/bump_version.py` (đồng bộ `pyproject.toml` + `videodubber/__init__.py`).
- Tag `vX.Y.Z` phải khớp version — workflow release kiểm.
- Push, tạo repo, tag, publish release, xoá tag/branch từ xa: **hỏi người dùng trước, mỗi lần**.
- Trước khi công khai repo lần đầu: squash lịch sử nếu commit cũ từng chứa dữ liệu nhạy cảm.
