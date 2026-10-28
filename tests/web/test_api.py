import shutil
import time

import pytest
from fastapi.testclient import TestClient

from videodubber.media import ffmpeg
from web.server import COOKIE, TOKEN_HEADER, create_app

TOKEN = "test-token"
HOST = "testserver"
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")


@pytest.fixture
def client():
    c = TestClient(create_app(TOKEN, {HOST}))
    c.headers[TOKEN_HEADER] = TOKEN
    return c


@pytest.fixture
def video_bytes(tmp_path):
    out = tmp_path / "v.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=3", "-f", "lavfi", "-i", "sine=duration=3", "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(out))
    return out.read_bytes()


def test_requires_token():
    c = TestClient(create_app(TOKEN, {HOST}))
    assert c.get("/api/langs").status_code == 401
    assert c.get("/").status_code == 401
    r = c.get(f"/?t={TOKEN}", follow_redirects=False)
    assert r.status_code == 303 and COOKIE in r.headers["set-cookie"]


def test_bad_host_and_origin(client):
    assert client.get("/api/langs", headers={"host": "evil.com"}).status_code == 403
    assert client.get("/api/langs", headers={"origin": "http://evil.com"}).status_code == 403


def test_index_has_csp(client):
    r = client.get("/")
    assert r.status_code == 200 and "default-src 'self'" in r.headers["content-security-policy"]


def test_meta(client):
    codes = [x["code"] for x in client.get("/api/langs").json()["items"]]
    assert "es" in codes and "ja" in codes
    assert {"offline_voice", "separate", "translate_api", "missing_models", "download"} <= set(
        client.get("/api/capabilities").json())


def test_log_endpoint(client):
    r = client.get("/api/log")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")


def test_path_traversal_blocked(client):
    assert client.get("/api/templates/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/batches/abcdef123456/files/..%2Fx.mp4").status_code == 404


@needs_ffmpeg
def test_upload_edit_preview_and_run(client, video_bytes, tmp_path):
    wav = tmp_path / "v.wav"
    ffmpeg("-f", "lavfi", "-i", "sine=duration=1", str(wav))
    wav_bytes = wav.read_bytes()
    files = {"video": ("Video gốc.mp4", video_bytes, "video/mp4")}
    r = client.post("/api/templates", files=files, data={"name": "Thử"})
    assert r.status_code == 200, r.text
    tpl = r.json()
    assert (tpl["width"], tpl["height"]) == (360, 640) and tpl["cover"]["w"] == 360
    assert client.post("/api/templates", files={"video": ("x.txt", b"hi", "text/plain")}).status_code == 422

    tpl["captions"] = [{"start": 0, "end": 2, "text": "Bonjour"}]
    tpl["width"] = 9999  # trường do tool đo — server phải bỏ qua
    saved = client.put(f"/api/templates/{tpl['id']}", json=tpl).json()
    assert saved["width"] == 360 and saved["captions"][0]["text"] == "Bonjour"
    bad = dict(tpl, captions=[{"start": 2, "end": 1, "text": "x"}])
    assert client.put(f"/api/templates/{tpl['id']}", json=bad).status_code == 422

    assert client.get(f"/api/templates/{tpl['id']}/voicefile").status_code == 404
    up = client.post(f"/api/templates/{tpl['id']}/voicefile", files={"file": ("giọng.wav", wav_bytes, "audio/wav")})
    assert up.status_code == 200 and up.json()["audio_mode"] == "uploaded_voice", up.text
    assert client.get(f"/api/templates/{tpl['id']}/voicefile").status_code == 200
    assert client.post(f"/api/templates/{tpl['id']}/voicefile", files={"file": ("x.txt", b"x")}).status_code == 422
    body = {**saved, "voice_file": None, "audio_mode": "original"}
    kept = client.put(f"/api/templates/{tpl['id']}", json=body).json()
    assert kept["voice_file"] == up.json()["voice_file"]  # file voice không bị xoá do giao diện gửi thiếu
    tpl = kept

    assert client.get(f"/api/templates/{tpl['id']}/frame?t=1").headers["content-type"] == "image/jpeg"
    pv = client.post(f"/api/templates/{tpl['id']}/preview", json={"text": "¿Ya probaste?", "t": 1, "lang": "es"})
    assert pv.status_code == 200 and pv.content[:2] == b"\xff\xd8"

    prompt = client.post("/api/translate/prompt", json={"template_id": tpl["id"], "langs": ["es"], "hooks": 2}).json()
    assert "Bonjour" in prompt["prompt"]
    reply = '```json\n{"es": {"hooks": [["Hola"]], "voice": []}}```'
    parsed = client.post("/api/translate/parse", json={"text": reply})
    assert parsed.json()["result"]["es"]["hooks"] == [["Hola"]]

    body = {"template_id": tpl["id"], "variants": [{"lang": "es", "captions": ["Hola"], "hook": "h1"},
                                                   {"lang": "es", "captions": ["Qué tal"], "hook": "h2"}]}
    assert client.post("/api/jobs", json={**body, "variants": [{"lang": "es", "captions": []}]}).status_code == 422
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 200, r.text
    bid = r.json()["batch_id"]
    for _ in range(600):
        job = client.get("/api/jobs").json()
        if job["status"] != "running":
            break
        time.sleep(0.1)
    assert job["status"] == "done" and job["ok"] == 2, job
    name = job["items"][0]["output"].replace("\\", "/").rsplit("/", 1)[-1]
    v = client.get(f"/api/batches/{bid}/files/{name}")
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    z = client.get(f"/api/batches/{bid}/zip")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    assert any(b["id"] == bid for b in client.get("/api/batches").json()["items"])


@needs_ffmpeg
def test_upload_copies_text_and_runs_group(client, video_bytes):
    first = client.post("/api/templates", files={"video": ("A.mp4", video_bytes, "video/mp4")}).json()
    first["captions"] = [{"start": 0, "end": 2, "text": "Bonjour"}]
    first["style"]["center_y"] = 200
    client.put(f"/api/templates/{first['id']}", json=first)
    r = client.post("/api/templates", files={"video": ("B có dấu.mp4", video_bytes, "video/mp4")},
                    data={"copy_from": first["id"]})
    assert r.status_code == 200, r.text
    second = r.json()
    assert second["captions"][0]["text"] == "Bonjour" and second["style"]["center_y"] == 200
    assert second["warnings"] == []
    bad = client.post("/api/templates", files={"video": ("C.mp4", video_bytes, "video/mp4")},
                      data={"copy_from": "khongtontai"})
    assert bad.status_code == 404

    body = {"template_id": first["id"], "template_ids": [first["id"], second["id"]],
            "variants": [{"lang": "es", "captions": ["Hola"], "hook": "h1"}]}
    assert client.post("/api/jobs", json={**body, "template_ids": [first["id"], "zzzzzz9999"]}).status_code == 404
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 200, r.text
    for _ in range(600):
        job = client.get("/api/jobs").json()
        if job["status"] != "running":
            break
        time.sleep(0.1)
    assert job["status"] == "done" and job["ok"] == 2 and job["total"] == 2, job


def test_draft_api(client):
    did = "d1a2b3c4d5e6"
    assert client.get(f"/api/drafts/{did}").json() == {}
    assert client.put(f"/api/drafts/{did}", json={"picked": ["es"]}).status_code == 200
    assert client.get(f"/api/drafts/{did}").json() == {"picked": ["es"]}
    assert client.put(f"/api/drafts/{did}", json=[1, 2]).status_code == 422
    assert client.put("/api/drafts/bad..id", json={}).status_code == 404
    assert client.delete(f"/api/drafts/{did}").status_code == 200
    assert client.get(f"/api/drafts/{did}").json() == {}


def test_models_download_unlocks_separation(client, tmp_path, monkeypatch):
    from videodubber import defaults as D
    from videodubber import modelstore

    monkeypatch.delenv("VIDEODUBBER_MODELS", raising=False)
    monkeypatch.setattr(D, "resource_root", lambda: tmp_path / "app")
    src = tmp_path / "fake.onnx"
    src.write_bytes(b"x" * 1000)
    monkeypatch.setattr(modelstore, "FILES", {modelstore.SEPARATION: src.as_uri()})
    caps = client.get("/api/capabilities").json()
    assert caps["separate"] is False and caps["missing_models"] == [modelstore.SEPARATION]
    assert client.post("/api/models/download").json()["started"] is True
    for _ in range(100):
        caps = client.get("/api/capabilities").json()
        if not caps["download"]["running"]:
            break
        time.sleep(0.05)
    assert caps["separate"] is True and caps["missing_models"] == [] and caps["download"]["error"] is None
    assert client.post("/api/models/download").json()["started"] is False
