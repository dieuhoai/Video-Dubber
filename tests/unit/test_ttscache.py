"""Bộ nhớ đệm giọng đọc: cùng câu + ngôn ngữ + giọng chỉ đọc 1 lần; render lại không đọc lại."""
import shutil
from pathlib import Path

from videodubber import defaults as D
from videodubber.langs import get_lang
from videodubber.processor import _synth_cached


class CountingTTS:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def synth(self, text, lang, gender, out: Path) -> Path:
        self.calls += 1
        shutil.copyfile(Path(__file__), out)  # file WAV giả, chỉ cần có nội dung
        return out


def test_same_line_is_synthesized_once(tmp_path):
    tts = CountingTTS()
    lang = get_lang("es")
    a = _synth_cached(tts, "Hola", lang, "f", tmp_path / "a.wav")
    b = _synth_cached(tts, "Hola", lang, "f", tmp_path / "b.wav")
    assert tts.calls == 1
    assert a.read_bytes() == b.read_bytes()
    _synth_cached(tts, "Hola", lang, "m", tmp_path / "c.wav")  # khác giọng → đọc lại
    _synth_cached(tts, "Hola", get_lang("fr"), "f", tmp_path / "d.wav")  # khác ngôn ngữ → đọc lại
    assert tts.calls == 3
    assert (D.DATA_DIR / "tts_cache").is_dir()
