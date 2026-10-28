"""Tách nhạc nền khỏi giọng nói bằng mô hình UVR MDX-Net (ONNX, chạy CPU, không cần PyTorch).

Mô hình mặc định: UVR-MDX-NET-Inst_HQ_3 (đầu ra = nhạc không lời). Tham số theo bảng model_data của UVR.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .media import MediaError, ffmpeg

SR = 44100


@dataclass(frozen=True)
class MdxParams:
    n_fft: int = 6144
    hop: int = 1024
    dim_f: int = 3072
    dim_t: int = 256
    compensate: float = 1.022


def _stft(np, x, p: MdxParams):
    """x: [2, L] → [4, dim_f, T] (re/im của 2 kênh), giống torch.stft(center=True, hann periodic)."""
    win = np.hanning(p.n_fft + 1)[:-1].astype(np.float32)
    pad = p.n_fft // 2
    xp = np.pad(x, ((0, 0), (pad, pad)), mode="reflect")
    t = 1 + (xp.shape[1] - p.n_fft) // p.hop
    idx = np.arange(p.n_fft)[None, :] + p.hop * np.arange(t)[:, None]
    frames = xp[:, idx] * win  # [2, T, n_fft]
    spec = np.fft.rfft(frames, axis=-1).transpose(0, 2, 1)  # [2, F, T]
    out = np.stack([spec.real, spec.imag], axis=1).reshape(4, spec.shape[1], t)
    return out[:, : p.dim_f, :].astype(np.float32)


def _istft(np, s, p: MdxParams, length: int):
    n_bins = p.n_fft // 2 + 1
    s = np.concatenate([s, np.zeros((4, n_bins - s.shape[1], s.shape[2]), np.float32)], axis=1)
    s = s.reshape(2, 2, n_bins, -1)
    spec = (s[:, 0] + 1j * s[:, 1]).transpose(0, 2, 1)  # [2, T, F]
    frames = np.fft.irfft(spec, n=p.n_fft, axis=-1)
    win = np.hanning(p.n_fft + 1)[:-1]
    t = frames.shape[1]
    total = p.n_fft + p.hop * (t - 1)
    out = np.zeros((2, total))
    norm = np.zeros(total)
    for i in range(t):
        out[:, i * p.hop: i * p.hop + p.n_fft] += frames[:, i] * win
        norm[i * p.hop: i * p.hop + p.n_fft] += win ** 2
    out /= np.maximum(norm, 1e-8)
    pad = p.n_fft // 2
    return out[:, pad: pad + length]


def separate_instrumental(model: Path, wav_in: Path, wav_out: Path, p: MdxParams | None = None) -> Path:
    try:
        import numpy as np
        import onnxruntime as ort
        import soundfile as sf
    except ImportError as e:
        raise MediaError("Máy đang thiếu thư viện tách nhạc — quay lại bước 1, bấm “Cài & tải đủ để tách nhạc” "
                         "rồi chạy lại.") from e
    if not model.is_file():
        raise MediaError(f"Không thấy mô hình tách nhạc {model.name} — chạy scripts/get_models.py để tải.")
    p = p or MdxParams()
    mix, sr = sf.read(str(wav_in), dtype="float32", always_2d=True)
    if sr != SR or mix.shape[1] != 2:
        raise MediaError("File âm thanh cần stereo 44,1 kHz")
    mix = mix.T  # [2, L]
    n = mix.shape[1]
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    chunk = p.hop * (p.dim_t - 1)
    trim = p.n_fft // 2
    gen = chunk - 2 * trim
    pad = gen - n % gen
    padded = np.concatenate([np.zeros((2, trim), np.float32), mix, np.zeros((2, pad + trim), np.float32)], axis=1)
    pieces = []
    for i in range(0, n + pad, gen):
        wave = padded[:, i: i + chunk]
        spec = _stft(np, wave, p)[None]
        pred = sess.run(None, {inp: spec})[0][0]
        pieces.append(_istft(np, pred, p, chunk)[:, trim: trim + gen])
    inst = np.concatenate(pieces, axis=1)[:, :n] * p.compensate
    sf.write(str(wav_out), inst.T.astype(np.float32), SR)
    return wav_out


def extract_stereo(video: Path, out: Path) -> Path:
    ffmpeg("-i", str(video), "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_f32le", str(out), timeout=300)
    return out
