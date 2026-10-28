"""Bản nháp phiên làm việc: chữ, ngôn ngữ, bản dịch được lưu trên máy, chỉ mất khi bấm Reset."""
import pytest

from videodubber import store


def test_draft_roundtrip_and_delete():
    data = {"group": [{"id": "abcdef123456", "name": "Video có dấu"}], "picked": ["es"],
            "tr": {"es": {"hooks": "¿Ya probaste?\nHola", "captions": [], "voice": [], "syncHook": True}}}
    store.save_draft("d1a2b3c4d5e6", data)
    assert store.load_draft("d1a2b3c4d5e6") == data
    store.delete_draft("d1a2b3c4d5e6")
    assert store.load_draft("d1a2b3c4d5e6") is None
    store.delete_draft("d1a2b3c4d5e6")  # xoá lần 2 không lỗi


def test_draft_rejects_bad_id_and_huge_data():
    with pytest.raises(FileNotFoundError):
        store.save_draft("../../etc", {})
    with pytest.raises(ValueError, match="lớn"):
        store.save_draft("d1a2b3c4d5e6", {"x": "a" * 3_000_000})
