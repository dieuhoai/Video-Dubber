import pytest

from videodubber.io_utils import atomic_write_text, read_json
from videodubber.models import Preset
from videodubber.preset_io import list_presets, load_preset, save_preset


def test_atomic_write_leaves_no_temp(tmp_path):
    p = tmp_path / "x" / "f.txt"
    atomic_write_text(p, "abc")
    assert p.read_text(encoding="utf-8") == "abc"
    assert [f.name for f in p.parent.iterdir()] == ["f.txt"]


def test_read_json_default(tmp_path):
    assert read_json(tmp_path / "missing.json", {"a": 1}) == {"a": 1}


def test_builtin_and_user_presets():
    assert "default" in list_presets()
    save_preset(Preset(name="mine", uppercase=True))
    assert load_preset("mine").uppercase is True
    assert "mine" in list_presets()


@pytest.mark.parametrize("bad", ["../evil", "a/b", "", "x" * 81])
def test_rejects_unsafe_names(bad):
    with pytest.raises(ValueError):
        load_preset(bad)
