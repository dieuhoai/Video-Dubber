"""Smoke test giao diện bằng Playwright: upload → caption → chọn ngôn ngữ → 2 câu hook → 2 video, không lỗi JS."""
import shutil
import socket
import threading
import time

import pytest

from videodubber.media import ffmpeg

pw = pytest.importorskip("playwright.sync_api")
pytestmark = [pytest.mark.ui, pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")]

TOKEN = "ui-test"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server():
    import uvicorn

    from web.server import create_app
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(create_app(TOKEN, {f"127.0.0.1:{port}"}), host="127.0.0.1", port=port,
                                        log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(5)


@pytest.fixture
def video(tmp_path):
    out = tmp_path / "Ads gốc.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=3", "-f", "lavfi", "-i", "sine=duration=3", "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out))
    return out


def _launch(p):
    for kw in ({}, {"executable_path": "/opt/pw-browsers/chromium"}):
        try:
            return p.chromium.launch(**kw)
        except Exception:  # noqa: BLE001 — thử đường dẫn Chromium khác
            continue
    pytest.skip("Chưa cài Chromium")


@pytest.mark.parametrize("viewport", [(1440, 900), (375, 812)])
def test_full_flow(server, video, viewport):
    with pw.sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/?t={TOKEN}")
        page.get_by_test_id("tpl-file").set_input_files(str(video))
        page.get_by_test_id("tpl-upload").click()
        pw.expect(page.get_by_test_id("frame")).to_be_visible(timeout=15_000)
        pw.expect(page.get_by_test_id("next-1")).to_be_disabled()  # chưa có chữ caption → không cho đi tiếp
        pw.expect(page.get_by_test_id("need-caption")).to_be_visible()
        page.get_by_test_id("caption-text").first.fill("As-tu essayé ?")  # dòng caption được tạo sẵn
        pw.expect(page.get_by_test_id("need-caption")).to_be_hidden()
        page.get_by_test_id("next-1").click()
        page.get_by_test_id("lang-es").check()
        page.get_by_test_id("next-2").click()
        page.get_by_test_id("hooks-es").fill("¿Ya probaste?\n¡Tarjetas con IA!")
        pw.expect(page.get_by_test_id("variant-count")).to_contain_text("2")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "tràn ngang"
        page.get_by_test_id("run").click()
        pw.expect(page.get_by_test_id("status")).to_contain_text("2/2", timeout=120_000)
        pw.expect(page.locator("video")).to_have_count(2)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "tràn ngang"
        browser.close()
        assert not errors, errors
