"""Smoke test giao diện bằng Playwright: nhập đường dẫn → chạy → hoàn tất, không lỗi JS."""
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

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


@pytest.mark.parametrize("viewport", [(1440, 900), (375, 812)])
def test_run_flow(server, sample_input, tmp_path, viewport):
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chưa cài Chromium: {e}")
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/?t={TOKEN}")
        page.get_by_test_id("input-dir").fill(str(sample_input))
        page.get_by_test_id("output-dir").fill(str(tmp_path / "out"))
        page.get_by_test_id("run").click()
        pw.expect(page.get_by_test_id("status")).to_contain_text("3/3", timeout=10_000)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "tràn ngang"
        browser.close()
        assert not errors, errors
