import pytest

from videodubber.models import JobRequest, Preset
from videodubber.processor import run_job, scan


def test_scan_filters_by_extension(sample_input):
    names = sorted(p.name for p in scan(sample_input, Preset(name="p", extensions=["txt", ".MD"])))
    assert names == ["Tiếng Việt 'nháy'.md", "a.txt", "bad.txt"]


def test_run_job_isolates_failures(sample_input, tmp_path):
    out = tmp_path / "out"
    seen = []
    preset = Preset(name="p", extensions=[".txt", ".md"])
    res = run_job(JobRequest(input_dir=sample_input, output_dir=out, preset=preset),
                  on_progress=lambda d, t, it: seen.append((d, t)))
    assert len(res.items) == 3 and res.ok_count == 2
    assert [f.source.name for f in res.failed] == ["bad.txt"]
    assert seen[-1] == (3, 3)
    assert (out / "a.txt").read_text(encoding="utf-8") == "hello world\nline two\n"
    assert (out / "sub" / "Tiếng Việt 'nháy'.md").exists()


def test_uppercase_option(sample_input, tmp_path):
    run_job(JobRequest(input_dir=sample_input, output_dir=tmp_path / "o", preset=Preset(name="p", uppercase=True)))
    assert (tmp_path / "o" / "a.txt").read_text(encoding="utf-8").startswith("HELLO")


def test_stop_early(sample_input, tmp_path):
    res = run_job(JobRequest(input_dir=sample_input, output_dir=tmp_path / "o", preset=Preset(name="p")),
                  should_stop=lambda: True)
    assert res.items == []


def test_output_must_differ_from_input(sample_input):
    with pytest.raises(ValueError):
        run_job(JobRequest(input_dir=sample_input, output_dir=sample_input, preset=Preset(name="p")))


def test_preset_requires_extension():
    with pytest.raises(ValueError):
        Preset(name="p", extensions=[" "])
