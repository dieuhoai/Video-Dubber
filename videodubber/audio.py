"""Âm thanh: tách nhạc nền, khớp thời lượng voice, trộn voice + nhạc (ducking, loudnorm −14 LUFS)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .media import MediaError, audio_duration, ffmpeg, loudness

MAX_SPEED = 1.15  # nhanh hơn nữa nghe gấp gáp → bắt rút gọn câu
TARGET_LUFS = -14.0


@dataclass
class Fit:
    """Kết quả khớp 1 câu voice vào khe thời gian của nó."""

    index: int
    natural: float  # độ dài đọc tự nhiên (giây)
    slot: float  # thời gian có (tới câu sau / hết video)
    speed: float  # hệ số atempo đã dùng (≥ 1)

    @property
    def too_long(self) -> bool:
        return self.natural / self.slot > MAX_SPEED + 1e-6


def speed_for(natural: float, slot: float) -> float:
    """Chỉ tăng tốc khi cần, tối đa 1,15×; ngắn hơn khe thì giữ nguyên tốc độ."""
    if slot <= 0:
        return MAX_SPEED
    return round(min(max(natural / slot, 1.0), MAX_SPEED), 3)


def slots(starts: list[float], ends: list[float], duration: float) -> list[float]:
    """Khe của mỗi câu: tới đầu câu kế tiếp (hoặc hết video), nhưng không ít hơn độ dài người dùng đặt."""
    out = []
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else duration
        out.append(max(min(nxt, duration) - s, ends[i] - s, 0.1))
    return out


def fit_clip(src: Path, out: Path, index: int, slot: float) -> Fit:
    nat = audio_duration(src)
    sp = speed_for(nat, slot)
    # Cắt cứng ở cuối khe (fade 60 ms) để voice không đè câu sau khi câu quá dài.
    af = f"atempo={sp},atrim=0:{slot:.3f},afade=t=out:st={max(slot - 0.06, 0):.3f}:d=0.06"
    ffmpeg("-i", str(src), "-af", af, "-ac", "1", "-ar", "44100", str(out), timeout=120)
    return Fit(index, nat, slot, sp)


SEPARATION_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"


def separate_music(video: Path, out_dir: Path) -> Path:
    """Tách nhạc nền khỏi giọng gốc (MDX-Net ONNX). Chạy 1 lần cho mỗi template, kết quả được cache."""
    from .defaults import models_dir
    from .separate import extract_stereo, separate_instrumental

    out_dir.mkdir(parents=True, exist_ok=True)
    mixed = extract_stereo(video, out_dir / "mix.wav")
    return separate_instrumental(models_dir() / SEPARATION_MODEL, mixed, out_dir / "music.wav")


def normalize(src: Path, out: Path, target: float = TARGET_LUFS) -> Path:
    """Đưa về đúng −14 LUFS: đo trước rồi chỉnh gain tuyến tính (loudnorm 1 lượt sai nhiều với video ngắn),
    sau đó limiter chặn đỉnh để không bị clip."""
    measured = loudness(src)
    gain = 0.0 if measured is None or measured < -70 else target - measured
    ffmpeg("-i", str(src), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:level=disabled", "-ac", "2",
           "-ar", "44100", str(out), timeout=300)
    return out


def mix(voice_clips: list[tuple[Path, float]], music: Path | None, duration: float, out: Path,
        music_gain_db: float = -4.0) -> Path:
    """Đặt từng câu voice đúng mốc, nhạc ducking dưới voice, chuẩn hoá −14 LUFS, cắt đúng thời lượng video."""
    args: list[str] = []
    parts: list[str] = []
    for i, (clip, start) in enumerate(voice_clips):
        args += ["-i", str(clip)]
        ms = max(round(start * 1000), 0)
        parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
    n = len(voice_clips)
    if n:
        parts.append("".join(f"[v{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
                     f"apad=whole_dur={duration:.3f}[voice]")
    if music is not None:
        args += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{duration:.3f},"
                     f"volume={music_gain_db}dB[mus]")
        if n:
            parts.append("[voice]asplit[voice1][sc]")
            parts.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck]")
            parts.append("[duck][voice1]amix=inputs=2:normalize=0[mixed]")
        else:
            parts.append("[mus]anull[mixed]")
    elif n:
        parts.append("[voice]anull[mixed]")
    else:
        raise MediaError("Không có voice và cũng không có nhạc — chọn “Giữ âm gốc” nếu chỉ đổi chữ.")
    parts.append(f"[mixed]aresample=44100,atrim=0:{duration:.3f},apad=whole_dur={duration:.3f}[out]")
    raw = out.with_name(out.stem + ".raw.wav")
    ffmpeg(*args, "-filter_complex", ";".join(parts), "-map", "[out]", "-ac", "2", "-ar", "44100", str(raw),
           timeout=600)
    normalize(raw, out)
    return out
