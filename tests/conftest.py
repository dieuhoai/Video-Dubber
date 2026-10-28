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
    monkeypatch.setattr(D, "DATA_DIR", tmp_path / "_user" / "data")
    monkeypatch.setattr(D, "SETTINGS_FILE", tmp_path / "_user" / "settings.json")




@pytest.fixture(autouse=True)
def no_real_update_check(monkeypatch):
    """Test không gọi GitHub thật để kiểm tra bản mới."""
    monkeypatch.setenv("VIDEODUBBER_UPDATE_URL", "file:///khong-co-ban-moi.json")
