"""Caption cũ phải bị xoá sạch kể cả khi caption mới ngắn hơn nhiều (lỗi: chữ cũ lộ ra 2 bên)."""
import re
import shutil
from pathlib import Path

import pytest

from videodubber.captions import build_ass
from videodubber.io_utils import atomic_write_text
from videodubber.media import ffmpeg, run
from videodubber.models import Box, CaptionStyle, TimedLine
from videodubber.render import render

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")]


def _ymax(video: Path, crop: str, t: float = 1.0) -> int:
    p = run(["ffmpeg", "-hide_banner", "-ss", str(t), "-i", str(video), "-frames:v", "1",
             "-vf", f"crop={crop},signalstats,metadata=print", "-f", "null", "-"])
    return int(re.findall(r"lavfi.signalstats.YMAX=(\d+)", p.stderr)[-1])


def test_short_caption_hides_wide_old_caption(tmp_path):
    src = tmp_path / "src.mp4"
    # Nền xám tối + "chữ cũ" trắng kéo gần hết bề ngang (giống caption gốc dài).
    stripes = ",".join(f"drawbox=x={x}:y=440:w=8:h=60:color=white:t=fill" for x in range(12, 350, 20))
    ffmpeg("-f", "lavfi", "-i", "color=c=0x303030:s=360x640:r=30:d=2", "-vf", stripes,
           "-c:v", "libx264", "-preset", "ultrafast", str(src))
    assert _ymax(src, "40:60:10:440") > 200  # có chữ cũ ở mép trái

    style = CaptionStyle(size=30, center_x=180, center_y=470, max_width=330, glow=False)
    captions = [TimedLine(start=0, end=2, text="x")]
    ass_text, _ = build_ass(captions, ["OK"], style, 360, 640)
    ass = tmp_path / "c.ass"
    atomic_write_text(ass, ass_text)
    out = render(src, ass, tmp_path / "out.mp4", 2.0, Box(x=0, y=400, w=360, h=140), captions, None,
                 keep_original_audio=False, workdir=tmp_path)
    left = _ymax(out, "40:60:10:440")
    assert left < 90, f"chữ cũ còn lộ ở mép trái (YMAX={left})"




def test_text_mode_removes_only_text_and_keeps_rest(tmp_path):
    """Nền chuyển động + lớp glow xanh đứng yên + "chữ" trắng: chỉ chữ bị xoá, glow và ảnh ngoài glow giữ nguyên."""
    import numpy as np

    from videodubber.clean import _read, clean_clip, text_mask

    src = tmp_path / "src.mp4"
    stripes = ",".join(f"drawbox=x={x}:y=455:w=6:h=30:color=white:t=fill" for x in range(90, 270, 16))
    # Nền nhiễu thay đổi từng khung (giống video có chuyển động), lớp phủ đứng yên vẽ đè lên.
    ffmpeg("-f", "lavfi", "-i", "color=c=0x806040:s=360x640:r=30:d=2",
           "-vf", f"noise=alls=80:allf=t,drawbox=x=60:y=430:w=240:h=80:color=0x20E0E8:t=fill,{stripes}",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", str(src))
    box = Box(x=0, y=400, w=360, h=140)
    caps = [TimedLine(start=0, end=2, text="x")]
    res = clean_clip(src, box, caps, 30, tmp_path / "cache")
    assert res is not None, "phải tách được lớp phủ khỏi nền chuyển động"
    clip, start = res
    src_frames = _read(src, box, start, 2.0)
    mask = text_mask(src_frames)
    before = src_frames[30].astype(int)
    after = _read(clip, Box(x=0, y=0, w=360, h=140), 0, 2.0)[30].astype(int)
    stripe = after[55:85, 90:96]       # chỗ từng có chữ trắng (y 455–485 → 55–85 trong khung)
    assert stripe[..., 0].mean() < 120, "chữ trắng phải bị thay bằng màu glow (đỏ thấp)"
    diff = np.abs(after - before)
    glow = diff[70:75, 65:85].mean()  # nền glow cạnh chữ phải giữ nguyên
    assert glow < 4, f"nền glow bị thay đổi ({glow:.1f})"
    outside = diff[~mask].mean()  # ngoài nét chữ chỉ còn sai số nén (nền nhiễu là ca khó nhất để nén)
    assert outside < 10, f"ảnh ngoài nét chữ bị thay đổi ({outside:.1f})"
    assert mask.mean() < 0.15, "chỉ được xoá nét chữ, không phải cả khung"
    assert clean_clip(src, box, caps, 30, tmp_path / "cache")[0] == clip  # lần 2 dùng cache


def test_text_mode_falls_back_on_static_background(tmp_path):
    from videodubber.clean import clean_clip
    src = tmp_path / "still.mp4"
    ffmpeg("-f", "lavfi", "-i", "color=c=0x303030:s=360x640:r=30:d=1", "-vf",
           "drawbox=x=60:y=430:w=240:h=80:color=white:t=fill", "-c:v", "libx264", "-preset", "ultrafast", str(src))
    assert clean_clip(src, Box(x=0, y=400, w=360, h=140), [TimedLine(start=0, end=1, text="x")], 30,
                      tmp_path / "c") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")
def test_read_odd_sized_box(tmp_path):
    """Kéo vùng che ra kích thước/vị trí số lẻ (vd rộng 295) không được làm hỏng bước xoá chữ."""
    from videodubber.clean import _read
    from videodubber.media import ffmpeg
    from videodubber.models import Box
    v = tmp_path / "v.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=1", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", str(v))
    frames = _read(v, Box(x=33, y=101, w=295, h=83), 0, 0.5)
    assert frames.shape[1:] == (83, 295, 3) and frames.shape[0] >= 10
