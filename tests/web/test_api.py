import time

import pytest
from fastapi.testclient import TestClient

from web.server import COOKIE, TOKEN_HEADER, create_app

TOKEN = "test-token"
HOST = "testserver"


@pytest.fixture
def client():
    c = TestClient(create_app(TOKEN, {HOST}))
    c.headers[TOKEN_HEADER] = TOKEN
    return c


def test_requires_token():
    c = TestClient(create_app(TOKEN, {HOST}))
    assert c.get("/api/presets").status_code == 401
    assert c.get("/").status_code == 401
    r = c.get(f"/?t={TOKEN}", follow_redirects=False)
    assert r.status_code == 303 and COOKIE in r.headers["set-cookie"]


def test_bad_host_and_origin(client):
    assert client.get("/api/presets", headers={"host": "evil.com"}).status_code == 403
    assert client.get("/api/presets", headers={"origin": "http://evil.com"}).status_code == 403


def test_index_has_csp(client):
    r = client.get("/")
    assert r.status_code == 200 and "default-src 'self'" in r.headers["content-security-policy"]


def test_presets_roundtrip(client):
    assert "default" in client.get("/api/presets").json()["names"]
    assert client.put("/api/presets/mine", json={"extensions": ["md"]}).json()["extensions"] == [".md"]
    assert client.get("/api/presets/mine").status_code == 200
    assert client.get("/api/presets/..%2Fx").status_code == 404


def test_job_runs_to_done(client, sample_input, tmp_path):
    preset = client.get("/api/presets/default").json()
    body = {"input_dir": str(sample_input), "output_dir": str(tmp_path / "out"), "preset": preset}
    assert client.post("/api/jobs", json=body).status_code == 200
    for _ in range(100):
        job = client.get("/api/jobs").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done" and job["ok"] == 2 and len(job["failed"]) == 1


def test_job_validation(client, tmp_path):
    assert client.post("/api/jobs", json={"input_dir": str(tmp_path / "nope"), "output_dir": "x",
                                          "preset": {"name": "p"}}).status_code == 422
    assert client.post("/api/jobs", json={}).status_code == 422
