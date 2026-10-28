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


@pytest.fixture
def video2(tmp_path):
    out = tmp_path / "Video thứ hai.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=3", "-f", "lavfi", "-i", "sine=duration=3", "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out))
    return out


def test_multi_upload_keeps_text_and_drags(server, video, video2):
    with pw.sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/?t={TOKEN}")
        page.get_by_test_id("tpl-file").set_input_files([str(video), str(video2)])  # 2 video 1 lần
        page.get_by_test_id("tpl-upload").click()
        pw.expect(page.get_by_test_id("group")).to_be_visible(timeout=20_000)
        pw.expect(page.locator(".group-row")).to_have_count(2)
        page.get_by_test_id("caption-text").first.fill("Hook chung")

        # Kéo khung chữ mới xuống 60px trên màn hình → tâm caption đổi theo
        before = page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.style.center_y")
        box = page.get_by_test_id("drag-cap").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2 + 60, steps=5)
        page.mouse.up()
        after = page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.style.center_y")
        assert after > before
        # Kéo quá mép trên: khung chữ vẫn nằm trọn trong khung hình
        box = page.get_by_test_id("drag-cap").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] - 2000, steps=5)
        page.mouse.up()
        frame = page.get_by_test_id("frame").bounding_box()
        assert page.get_by_test_id("drag-cap").bounding_box()["y"] >= frame["y"] - 1
        # Khung xanh đè lên khung đỏ: nắm nhãn của khung đỏ vẫn kéo được khung đỏ
        page.get_by_test_id("drag-cap").focus()
        for _ in range(3):
            page.keyboard.press("Shift+ArrowDown")
        cy0 = page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.cover.y")
        tag = page.get_by_test_id("cover-tag").bounding_box()
        page.mouse.move(tag["x"] + 5, tag["y"] + 5)
        page.mouse.down()
        page.mouse.move(tag["x"] + 5, tag["y"] - 40, steps=5)
        page.mouse.up()
        assert page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.cover.y") < cy0
        cover_y = page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.cover.y")
        page.get_by_test_id("drag-cover").focus()
        page.keyboard.press("Shift+ArrowUp")
        assert page.evaluate("Alpine.$data(document.querySelector('.shell')).tpl.cover.y") == cover_y - 20

        # Sang video 2: chữ vẫn còn, vị trí giữ riêng
        page.locator(".group-row .link").nth(1).click()
        pw.expect(page.get_by_test_id("caption-text").first).to_have_value("Hook chung")

        # "Đổi video" rồi tải video khác: chữ được giữ
        page.get_by_test_id("tpl-change").click()
        pw.expect(page.get_by_test_id("keep-note")).to_be_visible()
        page.get_by_test_id("tpl-file").set_input_files(str(video))
        page.get_by_test_id("tpl-upload").click()
        pw.expect(page.get_by_test_id("caption-text").first).to_have_value("Hook chung", timeout=20_000)

        # Quay về nhóm 2 video, xuất 1 lần ra đủ 2 video
        page.get_by_test_id("tpl-change").click()
        page.get_by_test_id("tpl-file").set_input_files([str(video), str(video2)])
        page.get_by_test_id("tpl-upload").click()
        pw.expect(page.locator(".group-row")).to_have_count(2, timeout=20_000)
        page.get_by_test_id("next-1").click()
        page.get_by_test_id("lang-es").check()
        page.get_by_test_id("next-2").click()
        page.get_by_test_id("hooks-es").fill("¿Ya probaste?")
        pw.expect(page.get_by_test_id("variant-count")).to_contain_text("2")
        page.get_by_test_id("run").click()
        pw.expect(page.get_by_test_id("status")).to_contain_text("2/2", timeout=120_000)
        pw.expect(page.locator("video")).to_have_count(2)
        browser.close()
        assert not errors, errors


def test_text_kept_until_reset(server, video, video2):
    """Chữ, ngôn ngữ, hook chỉ mất khi bấm Reset — tải lại trang, đổi video, mở video cũ đều giữ nguyên."""
    with pw.sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(f"{server}/?t={TOKEN}")
        page.get_by_test_id("tpl-file").set_input_files(str(video))
        page.get_by_test_id("tpl-upload").click()
        page.get_by_test_id("caption-text").first.fill("Giữ tôi lại")
        page.get_by_test_id("next-1").click()
        page.get_by_test_id("lang-es").check()
        page.get_by_test_id("next-2").click()
        page.get_by_test_id("hooks-es").fill("Hola\nQué tal")
        page.wait_for_timeout(1200)  # chờ tự lưu nháp

        page.reload()  # tải lại trang: không mất gì
        pw.expect(page.get_by_test_id("hooks-es")).to_have_value("Hola\nQué tal", timeout=10_000)
        page.get_by_test_id("step-1").click()
        pw.expect(page.get_by_test_id("caption-text").first).to_have_value("Giữ tôi lại")

        # Tải video khác lên: chữ và hook vẫn còn
        page.get_by_test_id("tpl-change").click()
        page.get_by_test_id("tpl-file").set_input_files(str(video2))
        page.get_by_test_id("tpl-upload").click()
        pw.expect(page.get_by_test_id("caption-text").first).to_have_value("Giữ tôi lại", timeout=20_000)

        # Mở video cũ trong danh sách: vẫn giữ chữ đang làm
        page.get_by_test_id("tpl-change").click()
        page.locator(".list-row .link").last.click()
        pw.expect(page.get_by_test_id("caption-text").first).to_have_value("Giữ tôi lại")
        page.get_by_test_id("step-3").click()
        pw.expect(page.get_by_test_id("hooks-es")).to_have_value("Hola\nQué tal")

        # Màn hình thấp: khung hình phải khít video (không viền xám) để khung kéo thả đúng vị trí
        page.get_by_test_id("step-1").click()
        page.set_viewport_size({"width": 1280, "height": 560})
        page.wait_for_timeout(300)
        frame = page.locator(".frame").bounding_box()
        img = page.get_by_test_id("frame").evaluate("e => [e.naturalWidth, e.naturalHeight]")
        assert abs(frame["width"] / frame["height"] - img[0] / img[1]) < 0.02, (frame, img)
        page.set_viewport_size({"width": 1280, "height": 900})

        # Reset: mất hết, tải lại trang vẫn trống
        page.get_by_test_id("reset").click()
        pw.expect(page.get_by_test_id("tpl-upload")).to_be_visible()
        pw.expect(page.get_by_test_id("keep-note")).to_be_hidden()
        page.wait_for_timeout(800)
        page.reload()
        pw.expect(page.get_by_test_id("tpl-upload")).to_be_visible(timeout=10_000)
        pw.expect(page.get_by_test_id("reset")).to_be_hidden()
        browser.close()
        assert not errors, errors
