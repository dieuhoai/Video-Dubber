"""Tự cập nhật: kiểm tra bản mới, tải, cài đè đúng chỗ, script thay app chạy được trên đúng hệ điều hành."""
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from videodubber import __version__, updater
from videodubber import defaults as D


def _zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return path


def _fake_release(tmp_path: Path, monkeypatch, version: str, assets: dict[str, Path], zipball: Path | None = None):
    data = {"tag_name": f"v{version}", "body": "notes", "html_url": "https://example/rel",
            "assets": [{"name": n, "browser_download_url": p.as_uri()} for n, p in assets.items()],
            "zipball_url": zipball.as_uri() if zipball else ""}
    api = tmp_path / "latest.json"
    api.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("VIDEODUBBER_UPDATE_URL", api.as_uri())
    monkeypatch.setattr(updater, "_cache", {"at": 0.0, "rel": None})


def test_version_compare():
    assert updater.is_newer("0.1.10", "0.1.9")
    assert updater.is_newer("v1.0.0", "0.9.9")
    assert not updater.is_newer("0.1.5", "0.1.5")
    assert not updater.is_newer("0.1.4", "0.1.5")


def test_relaunch_keeps_args_and_forces_port_token():
    args = updater.relaunch_args(["--host", "0.0.0.0", "--port", "9000", "--token=abc", "--allow-host", "x"], 8766,
                                 "tok")
    assert args == ["--host", "0.0.0.0", "--allow-host", "x", "--port", "8766", "--token", "tok", "--no-browser"]


def test_status_reports_new_version(tmp_path, monkeypatch):
    z = _zip(tmp_path / "w.zip", {"VideoDubber.exe": "x"})
    _fake_release(tmp_path, monkeypatch, "99.0.0", {"VideoDubber-windows.zip": z})
    monkeypatch.setattr(updater, "install_kind", lambda: "windows")
    monkeypatch.setattr(updater, "install_target", lambda kind=None: tmp_path)
    st = updater.status(force=True)
    assert st["available"] and st["latest"]["version"] == "99.0.0" and not st["blocked"]
    assert st["latest"]["download"].endswith("w.zip")


def test_status_same_version_not_available(tmp_path, monkeypatch):
    _fake_release(tmp_path, monkeypatch, __version__, {})
    assert updater.status(force=True)["available"] is False


def test_offline_is_quiet(monkeypatch):
    monkeypatch.setenv("VIDEODUBBER_UPDATE_URL", "file:///khong/co/file.json")
    monkeypatch.setattr(updater, "_cache", {"at": 0.0, "rel": None})
    st = updater.status(force=True)
    assert st["available"] is False and "Không kiểm tra" in st["error"]


def test_source_update_overwrites_code_keeps_env(tmp_path, monkeypatch):
    root = tmp_path / "app"
    (root / "videodubber").mkdir(parents=True)
    (root / "videodubber" / "__init__.py").write_text('__version__ = "0.1.5"\n')
    (root / ".venv").mkdir()
    (root / ".venv" / "keep.txt").write_text("env")
    (root / "models").mkdir()
    (root / "models" / "m.onnx").write_text("model")
    top = "dieuhoai-Video-Dubber-abc123/"
    z = _zip(tmp_path / "src.zip", {
        top + "videodubber/__init__.py": '__version__ = "9.9.9"\n',
        top + "web/new.txt": "new",
        top + "pyproject.toml": 'dependencies = [\n  "pydantic>=2",\n]\n',
        top + "models/m.onnx": "SHOULD NOT OVERWRITE",
    })
    _fake_release(tmp_path, monkeypatch, "9.9.9", {}, zipball=z)
    monkeypatch.setattr(D, "resource_root", lambda: root)
    stages = []
    rel = updater.latest_release(force=True, kind="source")
    updater.perform(rel, [], lambda s, d, t: stages.append(s), kind="source", restart=False)
    assert '9.9.9' in (root / "videodubber" / "__init__.py").read_text()
    assert (root / "web" / "new.txt").read_text() == "new"
    assert (root / ".venv" / "keep.txt").read_text() == "env"
    assert (root / "models" / "m.onnx").read_text() == "model"
    assert stages[0] == "download" and stages[-1] == "restart"


def test_rejects_wrong_version_and_path_traversal(tmp_path):
    bad = _zip(tmp_path / "bad.zip", {"x/videodubber/__init__.py": '__version__ = "1.0.0"\n'})
    with pytest.raises(updater.UpdateError):
        updater.stage("source", bad, "2.0.0", tmp_path / "w1")
    evil = _zip(tmp_path / "evil.zip", {"../../evil.txt": "x"})
    with pytest.raises(updater.UpdateError):
        updater.stage("windows", evil, "2.0.0", tmp_path / "w2")
    notapp = _zip(tmp_path / "n.zip", {"readme.txt": "x"})
    with pytest.raises(updater.UpdateError):
        updater.stage("windows", notapp, "2.0.0", tmp_path / "w3")


def test_windows_flow_prepares_helper(tmp_path, monkeypatch):
    target = tmp_path / "VideoDubber"
    target.mkdir()
    z = _zip(tmp_path / "w.zip", {"VideoDubber.exe": "new", "_internal/lib.dll": "x"})
    _fake_release(tmp_path, monkeypatch, "99.0.0", {"VideoDubber-windows.zip": z})
    monkeypatch.setattr(updater, "install_target", lambda kind=None: target)
    rel = updater.latest_release(force=True, kind="windows")
    updater.perform(rel, ["--port", "1"], lambda *a: None, kind="windows", restart=False)
    script = (D.USER_DIR / "updates" / "update.cmd").read_text(encoding="ascii")
    assert "robocopy" in script and "%VD_TARGET%" in script
    assert (D.USER_DIR / "updates" / "v99.0.0" / "VideoDubber.exe").read_text() == "new"


def test_blockers(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "install_target", lambda kind=None: Path("/private/var/AppTranslocation/x/V.app"))
    assert "Applications" in updater.blocker("macos")
    monkeypatch.setenv("VIDEODUBBER_NO_UPDATE", "1")
    assert updater.blocker("source")


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _wait(marker: Path, secs: float = 60) -> bool:
    end = time.time() + secs
    while time.time() < end:
        if marker.exists():
            return True
        time.sleep(0.3)
    return False


@pytest.mark.skipif(sys.platform != "win32", reason="script .cmd chỉ chạy trên Windows")
def test_windows_script_really_replaces_and_relaunches(tmp_path):
    target, stage = tmp_path / "Công cụ (x86) %x", tmp_path / "stage"
    (target / "_internal").mkdir(parents=True)
    (target / "VideoDubber.exe").write_text("old")
    (target / "_internal" / "old.dll").write_text("old")
    (stage / "_internal").mkdir(parents=True)
    (stage / "VideoDubber.exe").write_text("new")
    (stage / "_internal" / "new.dll").write_text("new")
    marker = tmp_path / "relaunched.txt"
    launch = [sys.executable, "-c", f"open(r'{marker}', 'w').write('ok')"]
    script = tmp_path / "update.cmd"
    script.write_text(updater.windows_script(_dead_pid()), encoding="ascii")
    env = {**os.environ, **updater.windows_env(stage, target, launch, tmp_path / "u.log")}
    subprocess.run(["cmd.exe", "/c", str(script)], timeout=120, check=False, env=env)
    assert (target / "VideoDubber.exe").read_text() == "new"
    assert (target / "_internal" / "new.dll").exists()
    assert _wait(marker), (tmp_path / "u.log").read_text(errors="replace")


@pytest.mark.skipif(sys.platform == "win32", reason="script .sh cho Mac/Linux")
def test_posix_script_swaps_bundle_and_relaunches(tmp_path):
    target, new = tmp_path / "Apps it's" / "VideoDubber.app", tmp_path / "stage" / "VideoDubber.app"
    (target / "Contents").mkdir(parents=True)
    (target / "Contents" / "old").write_text("old")
    (new / "Contents").mkdir(parents=True)
    (new / "Contents" / "new").write_text("new")
    marker = tmp_path / "relaunched.txt"
    launch = [sys.executable, "-c", f"open(r'{marker}', 'w').write('ok')"]
    script = tmp_path / "update.sh"
    script.write_text(updater.posix_script(_dead_pid(), new, target, launch, tmp_path / "u.log"), encoding="utf-8")
    subprocess.run(["/bin/sh", str(script)], timeout=120, check=True)
    assert (target / "Contents" / "new").exists() and not (target / "Contents" / "old").exists()
    assert not Path(str(target) + ".old-update").exists()
    assert _wait(marker)


@pytest.mark.skipif(sys.platform != "darwin", reason="ditto chỉ có trên Mac")
def test_mac_stage_keeps_symlinks(tmp_path):
    app = tmp_path / "src" / "VideoDubber.app" / "Contents" / "MacOS"
    app.mkdir(parents=True)
    exe = app / "VideoDubber"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    (app / "link").symlink_to("VideoDubber")
    z = tmp_path / "m.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(tmp_path / "src" / "VideoDubber.app"), str(z)], check=True)
    out = updater.stage("macos", z, "9.9.9", tmp_path / "w")
    macos = out / "VideoDubber.app" / "Contents" / "MacOS"
    assert (macos / "link").is_symlink()
    assert (macos / "VideoDubber").stat().st_mode & 0o111
