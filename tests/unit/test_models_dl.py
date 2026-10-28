"""Thiếu mô hình AI (chạy từ mã nguồn, chưa chạy get_models) → tool tự tải được, không khoá tính năng mãi."""
from pathlib import Path

from videodubber import defaults as D
from videodubber import modelstore


def test_find_model_checks_user_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEODUBBER_MODELS", raising=False)
    monkeypatch.setattr(D, "resource_root", lambda: tmp_path / "app")
    assert modelstore.find_model("x.onnx") is None
    user = D.USER_DIR / "models"
    user.mkdir(parents=True)
    (user / "x.onnx").write_bytes(b"1" * 10)
    assert modelstore.find_model("x.onnx") == user / "x.onnx"


def test_download_writes_to_user_dir_and_reports_progress(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEODUBBER_MODELS", raising=False)
    monkeypatch.setattr(D, "resource_root", lambda: tmp_path / "app")
    src = tmp_path / "src.bin"
    src.write_bytes(b"a" * 50_000)
    monkeypatch.setattr(modelstore, "FILES", {"m.onnx": src.as_uri()})
    seen = []
    modelstore.download_all(on_progress=lambda name, done, total: seen.append((name, done, total)))
    assert modelstore.find_model("m.onnx") == D.USER_DIR / "models" / "m.onnx"
    assert seen and seen[-1][1] == 50_000
    assert not list((D.USER_DIR / "models").glob("*.part"))
    assert modelstore.missing() == []


def test_missing_lists_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEODUBBER_MODELS", raising=False)
    monkeypatch.setattr(D, "resource_root", lambda: tmp_path / "app")
    monkeypatch.setattr(modelstore, "FILES", {"a.onnx": "x", "b.bin": "y"})
    assert modelstore.missing() == ["a.onnx", "b.bin"]
    _ = Path
