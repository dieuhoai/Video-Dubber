import pytest
from pydantic import ValidationError

from videodubber.audio import MAX_SPEED, Fit, slots, speed_for
from videodubber.captions import build_ass, layout, wrap
from videodubber.langs import get_lang
from videodubber.models import Box, CaptionStyle, LangVariant, Template, TimedLine
from videodubber.processor import output_name, validate_variant
from videodubber.qa import check_glossary, check_voice


def tpl(**kw):
    base = dict(id="abc123", name="Bday", app="bdaycard", concept="hookIA", width=720, height=1280, duration=14.1,
                captions=[TimedLine(start=0, end=4.17, text="As-tu essayé les cartes d'anniversaire avec IA ?")],
                voice=[TimedLine(start=0.2, end=3.0, text="Tu as essayé ?"), TimedLine(start=4.5, end=7.6, text="Oui")],
                cover=Box(x=0, y=790, w=720, h=260))
    base.update(kw)
    return Template(**base)


def test_wrap_respects_width_and_keeps_words():
    st = CaptionStyle()
    lines = wrap("¿YA PROBASTE LAS TARJETAS DE CUMPLEAÑOS CON IA?", st.font, st.size, st.max_width)
    assert len(lines) == 2
    assert " ".join(lines) == "¿YA PROBASTE LAS TARJETAS DE CUMPLEAÑOS CON IA?"


def test_layout_shrinks_long_text_and_flags_it():
    st = CaptionStyle(max_lines=2)
    short = layout("Hola", st)
    assert short.scale == 1 and short.fits
    long = layout("palabra " * 60, st)
    assert long.size < st.size and not long.fits


def test_cjk_wraps_without_spaces():
    st = CaptionStyle(uppercase=False)
    lines = wrap("あなたはAIで誕生日カードを作ってみましたか？" * 2, st.font, st.size, st.max_width, spaces=False)
    assert len(lines) >= 2 and "".join(lines).startswith("あなたは")


def test_build_ass_has_glow_and_text_layers():
    st = CaptionStyle()
    ass, lays = build_ass([TimedLine(start=0, end=4.17, text="x")], ["Hola {mundo}"], st, 720, 1280)
    assert "PlayResX: 720" in ass and r"\pos(360,922)" in ass
    assert ass.count("Dialogue:") == 4 and "0:00:04.17" in ass
    assert "{mundo}" not in ass and "HOLA (MUNDO)" in ass  # chặn tag ASS chèn từ bản dịch
    with pytest.raises(ValueError):
        build_ass([TimedLine(start=0, end=1, text="x")], [], st, 720, 1280)


def test_speed_only_speeds_up_and_caps():
    assert speed_for(2.0, 3.0) == 1.0
    assert speed_for(3.3, 3.0) == 1.1
    assert speed_for(9.0, 3.0) == MAX_SPEED
    assert Fit(0, 3.6, 3.0, MAX_SPEED).too_long and not Fit(0, 3.3, 3.0, 1.1).too_long


def test_slots_run_until_next_line():
    assert slots([0.2, 4.5, 11.9], [3.0, 7.6, 13.0], 14.1) == pytest.approx([4.3, 7.4, 2.2])


def test_template_validation():
    with pytest.raises(ValidationError):
        TimedLine(start=3, end=2, text="x")
    with pytest.raises(ValidationError):
        tpl(cover=Box(x=0, y=1200, w=720, h=200))
    with pytest.raises(ValidationError):
        tpl(captions=[TimedLine(start=20, end=21, text="x")])
    with pytest.raises(ValidationError):
        CaptionStyle(glow_color="cyan")
    assert tpl(app="bday card!").app == "bdaycard"


def test_output_name_and_variant_checks():
    t = tpl(audio_mode="none")
    v = LangVariant(lang="es", captions=["hola"], voice=["a", "b"], hook="h2")
    assert output_name(t, v, 1) == "bdaycard_hookIA_es_f1_h2_9x16_v1.mp4"
    assert output_name(tpl(), v, 3).endswith("_es_orig_h2_9x16_v3.mp4")
    validate_variant(t, v)
    with pytest.raises(ValueError, match="câu thoại"):
        validate_variant(t, LangVariant(lang="es", captions=["hola"], voice=["a"]))
    with pytest.raises(ValueError, match="Chưa hỗ trợ"):
        validate_variant(t, LangVariant(lang="xx", captions=["hola"]))
    with pytest.raises(ValidationError):
        LangVariant(lang="es", hook="../x")


def test_qa_helpers():
    assert not check_voice([Fit(1, 5.0, 3.0, MAX_SPEED)]).ok
    assert check_voice([]).ok
    assert not check_glossary(["Bday AI"], ["Try Bday AI"], ["Prueba la app"]).ok
    assert check_glossary(["Bday AI"], ["Try Bday AI"], ["Prueba Bday AI"]).ok


def test_lang_catalog():
    assert get_lang("ar").rtl and not get_lang("ja").spaces
    assert get_lang("es").voice("m").startswith("es-ES")
