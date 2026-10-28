"""Đọc chữ thành giọng nói. Mặc định Microsoft Edge TTS (miễn phí, cần mạng); espeak-ng làm dự phòng offline."""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Protocol

from .langs import Lang
from .media import MediaError, ffmpeg, run


class TTS(Protocol):
    name: str

    def synth(self, text: str, lang: Lang, gender: str, out: Path) -> Path:
        """Ghi file WAV mono 44,1 kHz và trả về đường dẫn."""
        ...


def _to_wav(src: Path, out: Path) -> Path:
    # Cắt khoảng lặng đầu/cuối để khớp thời lượng chính xác hơn.
    ffmpeg("-i", str(src), "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
           "silenceremove=start_periods=1:start_threshold=-50dB,areverse", "-ac", "1", "-ar", "44100", str(out),
           timeout=120)
    return out


class EdgeTTS:
    name = "edge"

    def synth(self, text: str, lang: Lang, gender: str, out: Path) -> Path:
        try:
            import edge_tts
        except ImportError as e:
            raise MediaError("Chưa cài gói edge-tts (pip install edge-tts).") from e
        mp3 = out.with_suffix(".mp3")
        try:
            asyncio.run(edge_tts.Communicate(text, lang.voice(gender)).save(str(mp3)))
        except Exception as e:  # noqa: BLE001 — lỗi mạng/dịch vụ có nhiều loại, gom thành 1 câu dễ hiểu
            raise MediaError(f"Không tạo được giọng {lang.name} (cần kết nối Internet tới Microsoft): {e}") from e
        return _to_wav(mp3, out)


class EspeakTTS:
    """Giọng máy, nghe kém — chỉ để thử khi không có mạng."""

    name = "espeak"

    def synth(self, text: str, lang: Lang, gender: str, out: Path) -> Path:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            raise MediaError("Không có espeak-ng để đọc offline. Hãy dùng giọng Edge (cần mạng).")
        raw = out.with_suffix(".raw.wav")
        voice = f"{lang.espeak}+{'m3' if gender == 'm' else 'f3'}"
        run([exe, "-v", voice, "-s", "165", "-w", str(raw), text], timeout=120)
        return _to_wav(raw, out)


class KokoroTTS:
    """Giọng AI chạy offline trên máy chủ (mô hình Kokoro ONNX ~330 MB). Hỗ trợ một số ngôn ngữ."""

    name = "kokoro"
    MODEL = "kokoro-v1.0.onnx"
    VOICES = "voices-v1.0.bin"
    _engine = None

    @classmethod
    def available(cls) -> bool:
        from .modelstore import find_model
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError:
            return False
        return find_model(cls.MODEL) is not None and find_model(cls.VOICES) is not None

    def synth(self, text: str, lang: Lang, gender: str, out: Path) -> Path:
        if not lang.kokoro:
            raise MediaError(f"Giọng offline chưa hỗ trợ {lang.name}")
        import soundfile as sf
        from kokoro_onnx import Kokoro

        from .modelstore import find_model
        if KokoroTTS._engine is None:
            KokoroTTS._engine = Kokoro(str(find_model(self.MODEL)), str(find_model(self.VOICES)))
        code, vf, vm = lang.kokoro
        samples, sr = KokoroTTS._engine.create(text, voice=vm if gender == "m" else vf, speed=1.0, lang=code)
        raw = out.with_suffix(".raw.wav")
        sf.write(str(raw), samples, sr)
        return _to_wav(raw, out)


class AutoTTS:
    """Kokoro (offline) nếu ngôn ngữ hỗ trợ và đã có mô hình; còn lại dùng Edge TTS."""

    name = "auto"

    def __init__(self) -> None:
        self._kokoro = KokoroTTS() if KokoroTTS.available() else None
        self._edge = EdgeTTS()

    def synth(self, text: str, lang: Lang, gender: str, out: Path) -> Path:
        if self._kokoro and lang.kokoro:
            return self._kokoro.synth(text, lang, gender, out)
        return self._edge.synth(text, lang, gender, out)


def default_tts() -> TTS:
    choice = os.environ.get("VIDEODUBBER_TTS", "auto").lower()
    return {"espeak": EspeakTTS, "edge": EdgeTTS, "kokoro": KokoroTTS}.get(choice, AutoTTS)()
