"""Danh mục ngôn ngữ: tên hiển thị, giọng Edge TTS (nữ/nam), mã espeak-ng dự phòng, chiều viết."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Lang:
    code: str
    name: str
    voice_f: str
    voice_m: str
    espeak: str
    rtl: bool = False
    spaces: bool = True  # False: ngắt dòng theo ký tự (Nhật/Trung/Thái)
    kokoro: tuple[str, str, str] | None = None  # (mã ngôn ngữ, giọng nữ, giọng nam) của Kokoro offline

    def voice(self, gender: str) -> str:
        return self.voice_m if gender == "m" else self.voice_f

    def to_dict(self) -> dict:
        return asdict(self)


LANGS: dict[str, Lang] = {
    x.code: x
    for x in [
        Lang(
            "fr", "Français", "fr-FR-DeniseNeural", "fr-FR-HenriNeural", "fr", kokoro=("fr-fr", "ff_siwis", "ff_siwis")
        ),
        Lang(
            "en",
            "English (US)",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-us",
            kokoro=("en-us", "af_heart", "am_michael"),
        ),
        Lang("es", "Español", "es-ES-ElviraNeural", "es-ES-AlvaroNeural", "es", kokoro=("es", "ef_dora", "em_alex")),
        Lang(
            "es-MX",
            "Español (México)",
            "es-MX-DaliaNeural",
            "es-MX-JorgeNeural",
            "es-419",
            kokoro=("es", "ef_dora", "em_alex"),
        ),
        Lang("de", "Deutsch", "de-DE-KatjaNeural", "de-DE-ConradNeural", "de"),
        Lang("it", "Italiano", "it-IT-ElsaNeural", "it-IT-DiegoNeural", "it", kokoro=("it", "if_sara", "im_nicola")),
        Lang(
            "pt-BR",
            "Português (Brasil)",
            "pt-BR-FranciscaNeural",
            "pt-BR-AntonioNeural",
            "pt-br",
            kokoro=("pt-br", "pf_dora", "pm_alex"),
        ),
        Lang("nl", "Nederlands", "nl-NL-ColetteNeural", "nl-NL-MaartenNeural", "nl"),
        Lang("pl", "Polski", "pl-PL-ZofiaNeural", "pl-PL-MarekNeural", "pl"),
        Lang("tr", "Türkçe", "tr-TR-EmelNeural", "tr-TR-AhmetNeural", "tr"),
        Lang("ru", "Русский", "ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural", "ru"),
        Lang("ar", "العربية", "ar-SA-ZariyahNeural", "ar-SA-HamedNeural", "ar", rtl=True),
        Lang("hi", "हिन्दी", "hi-IN-SwaraNeural", "hi-IN-MadhurNeural", "hi", kokoro=("hi", "hf_alpha", "hm_omega")),
        Lang("id", "Bahasa Indonesia", "id-ID-GadisNeural", "id-ID-ArdiNeural", "id"),
        Lang("vi", "Tiếng Việt", "vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural", "vi"),
        Lang("th", "ไทย", "th-TH-PremwadeeNeural", "th-TH-NiwatNeural", "th", spaces=False),
        Lang(
            "ja",
            "日本語",
            "ja-JP-NanamiNeural",
            "ja-JP-KeitaNeural",
            "ja",
            spaces=False,
            kokoro=("ja", "jf_alpha", "jm_kumo"),
        ),
        Lang("ko", "한국어", "ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko"),
        Lang(
            "zh-CN",
            "中文 (简体)",
            "zh-CN-XiaoxiaoNeural",
            "zh-CN-YunxiNeural",
            "cmn",
            spaces=False,
            kokoro=("cmn", "zf_xiaobei", "zm_yunjian"),
        ),
    ]
}


def get_lang(code: str) -> Lang:
    try:
        return LANGS[code]
    except KeyError:
        raise ValueError(f"Chưa hỗ trợ ngôn ngữ “{code}”. Các mã có sẵn: {', '.join(LANGS)}") from None
