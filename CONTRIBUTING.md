# Đóng góp

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]      # macOS/Linux: .venv/bin/pip
python -m playwright install chromium
python -m pytest -q
```

Quy trình đầy đủ (spec → plan → TDD → review → release): [docs/LIFECYCLE.md](docs/LIFECYCLE.md).

Trước khi mở PR:

```bash
ruff check .
python -m pytest -q
python scripts/check_privacy.py
```

Commit theo [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `build:`, `ci:`.
