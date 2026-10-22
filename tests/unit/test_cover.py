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
