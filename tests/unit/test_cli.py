from videodubber.__main__ import main


def test_cli_run(sample_input, tmp_path, capsys):
    rc = main(["run", str(sample_input), str(tmp_path / "out")])
    out = capsys.readouterr()
    assert rc == 1  # bad.txt lỗi → exit 1
    assert "2/3" in out.out


def test_cli_bad_input(tmp_path, capsys):
    assert main(["run", str(tmp_path / "nope"), str(tmp_path / "out")]) == 2
    assert "Lỗi" in capsys.readouterr().err


def test_cli_presets(capsys):
    assert main(["presets"]) == 0
    assert "default" in capsys.readouterr().out
