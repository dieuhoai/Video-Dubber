"""Chạy trọn pipeline trên video tự sinh (ffmpeg testsrc). Giọng đọc giả bằng tiếng bíp để test không cần mạng."""
import shutil
from pathlib import Path

import pytest

from videodubber import store
from videodubber.media import ffmpeg, probe
from videodubber.models import BatchRequest, LangVariant, TimedLine
from videodubber.processor import run_batch

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")]


class BeepTTS:
    """Độ dài tiếng bíp tỉ lệ với số ký tự — đủ để kiểm tra khớp thời lượng."""

    name = "beep"

    def synth(self, text, lang, gender, out: Path) -> Path:
        ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={0.08 * len(text):.2f}", "-ac", "1", "-ar", "44100",
               str(out))
        return out


@pytest.fixture
def video(tmp_path) -> Path:
    out = tmp_path / "Video gốc 'nháy'.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=6", "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
           "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out))
    return out


def _setup(video, mode="none"):
    tpl = store.create_template(video, "Thiệp sinh nhật")
    tpl.captions = [TimedLine(start=0, end=2.5, text="As-tu essayé ?")]
    tpl.voice = [TimedLine(start=0.2, end=2.0, text="Tu as essayé ?"), TimedLine(start=3.0, end=5.0, text="Oui")]
    tpl.audio_mode = mode
    tpl.glossary = ["IA"]
    return store.save_template(tpl)


def test_batch_renders_each_hook_and_language(video):
    tpl = _setup(video)
    req = BatchRequest(template_id=tpl.id, variants=[
        LangVariant(lang="es", captions=["¿Ya probaste?"], voice=["Hola amigos", "Sí"], hook="h1"),
        LangVariant(lang="es", captions=["¡Tarjetas con IA!"], voice=["Hola amigos", "Sí"], hook="h2"),
        LangVariant(lang="ja", captions=["試しましたか？"], voice=["こんにちは", "はい"], hook="h1", gender="m"),
        LangVariant(lang="de", captions=["Text"], voice=["x" * 80, "ja"], hook="h1"),  # câu 1 quá dài
    ])
    seen, stages = [], []
    res = run_batch(req, on_progress=lambda d, t, it: seen.append((d, t)), tts=BeepTTS(), on_stage=stages.append)
    assert any("tạo giọng câu 1/2" in s for s in stages) and any("xuất video" in s for s in stages)
    assert seen[-1] == (4, 4) and res.ok_count == 4, [i.error for i in res.items]
    names = sorted(i.output.name for i in res.items)
    assert names[0].startswith("app_concept_de_f1_h1") and any("_ja_m1_h1_" in n for n in names)
    for it in res.items:
        info = probe(it.output)
        assert (info.width, info.height) == (360, 640) and info.has_audio
        checks = {c.name: c for c in it.checks}
        assert checks["Thời lượng"].ok and checks["Âm lượng"].ok, checks
    de = next(i for i in res.items if i.lang.startswith("de"))
    assert not {c.name: c for c in de.checks}["Tốc độ voice"].ok
    assert (store.batch_dir(res.batch_id) / "results.json").is_file()


def test_original_audio_mode_only_changes_text(video):
    tpl = _setup(video, mode="original")
    res = run_batch(BatchRequest(template_id=tpl.id, variants=[LangVariant(lang="es", captions=["Hola IA"])]),
                    tts=BeepTTS())
    item = res.items[0]
    assert item.ok and item.output.name.endswith("_es_orig_h1_9x16_v1.mp4")
    assert {c.name: c.ok for c in item.checks}["Âm lượng"]


def test_bad_variant_fails_fast(video):
    tpl = _setup(video)
    with pytest.raises(ValueError, match="caption"):
        run_batch(BatchRequest(template_id=tpl.id, variants=[LangVariant(lang="es", captions=[])]), tts=BeepTTS())
    with pytest.raises(ValueError, match="trùng"):
        v = LangVariant(lang="es", captions=["a"], voice=["a", "b"])
        run_batch(BatchRequest(template_id=tpl.id, variants=[v, v]), tts=BeepTTS())


def _tone(path: Path, seconds: float, freq: int = 330) -> Path:
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-ac", "1", "-ar", "44100", str(path))
    return path


def test_uploaded_voice_keeps_separated_music(video, tmp_path, monkeypatch):
    import videodubber.processor as P

    # Không có mô hình tách nhạc trong test → thay bằng 1 file "nhạc nền" giả.
    def fake_separate(vid, out):
        out.mkdir(parents=True, exist_ok=True)
        return _tone(out / "music.wav", 6, 110)

    monkeypatch.setattr(P, "separate_music", fake_separate)
    tpl = _setup(video)
    store.set_voice_file(tpl.id, _tone(tmp_path / "giọng của tôi.mp3", 4))
    tpl = store.load_template(tpl.id)
    assert tpl.audio_mode == "uploaded_voice" and tpl.voice_file and not tpl.uses_voice
    res = run_batch(BatchRequest(template_id=tpl.id, variants=[
        LangVariant(lang="en", captions=["Hook A"], hook="h1"),
        LangVariant(lang="en", captions=["Hook B"], hook="h2")]), tts=BeepTTS())
    assert res.ok_count == 2, [i.error for i in res.items]
    it = res.items[0]
    assert "_en_up_h1_" in it.output.name
    checks = {c.name: c for c in it.checks}
    assert checks["Voice tải lên"].ok and checks["Âm lượng"].ok and checks["Thời lượng"].ok, checks


def test_uploaded_voice_too_long_is_flagged(video, tmp_path, monkeypatch):
    import videodubber.processor as P

    monkeypatch.setattr(P, "separate_music", lambda vid, out: None)
    tpl = _setup(video)
    store.set_voice_file(tpl.id, _tone(tmp_path / "dai.wav", 9))
    res = run_batch(BatchRequest(template_id=tpl.id, variants=[LangVariant(lang="en", captions=["Hi"])]),
                    tts=BeepTTS())
    it = res.items[0]
    chk = {c.name: c for c in it.checks}["Voice tải lên"]
    assert it.ok and not chk.ok and "dài" in chk.detail
    assert abs(probe(it.output).duration - 6.0) < 0.05  # vẫn đúng thời lượng video, voice bị cắt


def test_uploaded_voice_missing_file(video):
    tpl = _setup(video)
    tpl.audio_mode = "uploaded_voice"
    store.save_template(tpl)
    with pytest.raises(Exception, match="voice"):
        run_batch(BatchRequest(template_id=tpl.id, variants=[LangVariant(lang="en", captions=["Hi"])]),
                  tts=BeepTTS())
