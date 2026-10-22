import os

import pytest


def pytest_collection_modifyitems(config, items):
    skip_real = pytest.mark.skip(reason="đặt VIDEODUBBER_REAL_DATA để chạy")
    for it in items:
        if "real" in it.keywords and not os.environ.get("VIDEODUBBER_REAL_DATA"):
            it.add_marker(skip_real)


@pytest.fixture(autouse=True)
def isolated_user_dir(tmp_path, monkeypatch):
    """Không bao giờ để test ghi vào thư mục cấu hình thật của người dùng."""
    from videodubber import defaults as D
    monkeypatch.setattr(D, "USER_DIR", tmp_path / "_user")
    monkeypatch.setattr(D, "USER_PRESET_DIR", tmp_path / "_user" / "presets")
    monkeypatch.setattr(D, "SETTINGS_FILE", tmp_path / "_user" / "settings.json")


@pytest.fixture
def sample_input(tmp_path):
    """Dữ liệu mẫu tự sinh — gồm cả edge case (tên có dấu, file lỗi encoding, file lồng thư mục)."""
    root = tmp_path / "in"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("hello world\nline two\n", encoding="utf-8")
    (root / "sub" / "Tiếng Việt 'nháy'.md").write_text("xin chào", encoding="utf-8")
    (root / "bad.txt").write_bytes(b"\xff\xfe\x00bad")
    (root / "skip.bin").write_bytes(b"\x00")
    return root
