"""Nhiều video dùng chung chữ: chép thiết lập sang video mới, chạy 1 batch cho nhiều video."""
import shutil
from pathlib import Path

import pytest

from videodubber import store
from videodubber.media import ffmpeg
from videodubber.models import BatchRequest, Box, LangVariant, TimedLine
from videodubber.processor import run_batch

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")


def _vid(tmp_path: Path, name: str, size: str, dur: int) -> Path:
    out = tmp_path / name
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=s={size}:r=30:d={dur}", "-f", "lavfi", "-i", f"sine=duration={dur}",
           "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out))
    return out


@pytest.fixture
def pair(tmp_path):
    a = store.create_template(_vid(tmp_path, "Video gốc A.mp4", "360x640", 6), "A")
    a.captions = [TimedLine(start=0, end=2, text="Hook"), TimedLine(start=2.5, end=5, text="Tải app")]
    a.voice = [TimedLine(start=0.2, end=1.8, text="Xin chào")]
    a.glossary = ["AI"]
    a.app, a.concept, a.cover_mode = "weather", "storm", "box"
    a.style.center_y, a.style.size, a.style.max_width = 400, 40, 300
    a.cover = Box(x=10, y=380, w=340, h=60)
    store.save_template(a)
    b = store.create_template(_vid(tmp_path, "Video B (dài 3s).mp4", "720x1280", 3), "B")
    return a, b


def test_copy_keeps_text_and_scales_positions(pair):
    a, b = pair
    tpl, warnings = store.copy_settings(a.id, b.id)
    assert [c.text for c in tpl.captions] == ["Hook", "Tải app"]
    assert tpl.captions[1].end == pytest.approx(3.0)  # cắt cho vừa video 3s
    assert [v.text for v in tpl.voice] == ["Xin chào"] and tpl.glossary == ["AI"]
    assert (tpl.app, tpl.concept, tpl.cover_mode) == ("weather", "storm", "box")
    assert (tpl.style.center_y, tpl.style.size, tpl.style.max_width) == (800, 80, 600)
    assert tpl.cover == Box(x=20, y=760, w=680, h=120)
    assert (tpl.width, tpl.height, tpl.duration) == (720, 1280, b.duration)  # thông số đo của video mới giữ nguyên
    assert any("cắt" in w for w in warnings)
    assert store.load_template(b.id).captions[0].text == "Hook"  # đã lưu


def test_copy_drops_lines_after_video_end(pair):
    a, b = pair
    a.captions.append(TimedLine(start=4, end=5.5, text="Cuối"))
    store.save_template(a)
    tpl, warnings = store.copy_settings(a.id, b.id)
    assert [c.text for c in tpl.captions] == ["Hook", "Tải app"]
    assert any("Cuối" in w for w in warnings)


def test_copy_brings_audio_files(pair, tmp_path):
    a, b = pair
    wav = tmp_path / "nhạc.wav"
    ffmpeg("-f", "lavfi", "-i", "sine=duration=1", str(wav))
    store.set_music(a.id, wav)
    tpl, _ = store.copy_settings(a.id, b.id)
    assert tpl.audio_mode == "music_file" and (store.template_dir(b.id) / tpl.music).is_file()


def test_batch_runs_every_video_in_group(pair):
    a, b = pair
    store.copy_settings(a.id, b.id)
    a.audio_mode = "original"
    store.save_template(a)
    bt = store.load_template(b.id)
    bt.audio_mode = "original"
    store.save_template(bt)
    req = BatchRequest(template_id=a.id, template_ids=[a.id, b.id],
                       variants=[LangVariant(lang="es", captions=["Hola", "Descarga"])])
    seen = []
    res = run_batch(req, on_progress=lambda d, t, it: seen.append((d, t)))
    assert res.ok_count == 2, [i.error for i in res.items]
    assert seen[-1] == (2, 2)
    names = sorted(i.output.name for i in res.items)
    assert len(set(names)) == 2 and all(n.startswith("weather_storm_") for n in names)
    assert all(i.output.parent == store.batch_dir(res.batch_id) for i in res.items)


def test_group_with_different_caption_count_fails_fast(pair):
    a, b = pair
    with pytest.raises(ValueError, match="caption"):
        run_batch(BatchRequest(template_id=a.id, template_ids=[a.id, b.id],
                               variants=[LangVariant(lang="es", captions=["Hola", "Descarga"])]))


@pytest.mark.parametrize("mode", ["text", "box"])
def test_odd_sized_cover_renders(tmp_path, mode):
    """Vùng che kéo bằng chuột có thể ra số lẻ — xuất video vẫn phải chạy."""
    tpl = store.create_template(_vid(tmp_path, "v.mp4", "360x640", 3), "Lẻ")
    tpl.captions = [TimedLine(start=0, end=2, text="Hook")]
    tpl.cover, tpl.cover_mode, tpl.audio_mode = Box(x=33, y=401, w=295, h=83), mode, "original"
    store.save_template(tpl)
    res = run_batch(BatchRequest(template_id=tpl.id, variants=[LangVariant(lang="es", captions=["Hola"])]))
    assert res.ok_count == 1, [i.error for i in res.items]
