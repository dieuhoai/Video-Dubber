"""Server web: mặc định chỉ nghe 127.0.0.1; chế độ máy chủ nội bộ (--host 0.0.0.0) cho cả team dùng chung.

Luôn giữ: token (link mời có ?t=…), kiểm Host/Origin, CSP chặt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import socket
import sys
import threading
import webbrowser
from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from videodubber import APP_NAME

from .api import batches, drafts, jobs, meta, templates, update
from .state import STATE

STATIC = Path(__file__).parent / "static"
COOKIE = "videodubber_token"
TOKEN_HEADER = "x-videodubber-token"
CSP = ("default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-eval'; connect-src 'self' ws: wss:; font-src 'self'; frame-ancestors 'none'")

EXPIRED_PAGE = f"""<!doctype html><html lang="vi"><meta charset="utf-8"><title>{APP_NAME}</title>
<style>body{{font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0}}
main{{max-width:420px;text-align:center;line-height:1.6}}</style>
<main><h1>Phiên đã hết hạn</h1><p>Vì lý do bảo mật, hãy mở lại giao diện từ ứng dụng.</p></main></html>"""


def create_app(token: str, allowed_hosts: Iterable[str]) -> FastAPI:
    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    hosts = set(allowed_hosts)
    STATE.token = token

    def _authorized(headers, cookies) -> bool:
        tok = cookies.get(COOKIE) or headers.get(TOKEN_HEADER)
        return bool(tok) and secrets.compare_digest(tok, token)

    def _host_ok(headers) -> bool:
        if hosts and headers.get("host", "") not in hosts:
            return False
        origin = headers.get("origin")
        return not (origin and origin.split("://", 1)[-1] not in hosts)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if not _host_ok(request.headers):
            return JSONResponse({"detail": "Host không hợp lệ"}, status_code=403)
        if path.startswith("/api") and not _authorized(request.headers, request.cookies):
            return JSONResponse({"detail": "Phiên hết hạn — mở lại từ ứng dụng"}, status_code=401)
        resp: Response = await call_next(request)
        if path.startswith("/static"):
            resp.headers["Cache-Control"] = "no-cache"
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    @app.get("/", include_in_schema=False)
    async def index(request: Request):
        t = request.query_params.get("t")
        if t and secrets.compare_digest(t, token):  # đổi token trên URL thành cookie rồi xoá khỏi URL
            r = RedirectResponse("/", status_code=303)
            r.set_cookie(COOKIE, token, httponly=True, samesite="strict")
            return r
        if not _authorized(request.headers, request.cookies):
            return HTMLResponse(EXPIRED_PAGE, status_code=401)
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html, headers={"Cache-Control": "no-store", "Content-Security-Policy": CSP})

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        if not _host_ok(sock.headers) or not _authorized(sock.headers, sock.cookies):
            await sock.close(code=4401)
            return
        await sock.accept()
        loop = asyncio.get_running_loop()
        q = STATE.add_client(loop)
        try:
            await sock.send_text(json.dumps({"type": "snapshot", **STATE.snapshot()}, default=str))
            while True:
                ev = await q.get()
                await sock.send_text(json.dumps(ev, ensure_ascii=False, default=str))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            STATE.remove_client(loop, q)

    for r in (templates.router, jobs.router, batches.router, meta.router, drafts.router, update.router):
        app.include_router(r)
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    return app


def _setup_log() -> None:
    """Ghi nhật ký ra file (bản .app trên Mac chạy ngầm, không có cửa sổ để xem lỗi)."""
    import logging
    from logging.handlers import RotatingFileHandler

    from videodubber import defaults as D
    D.USER_DIR.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(D.USER_DIR / "videodubber.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    lg = logging.getLogger("videodubber")
    lg.setLevel(logging.INFO)
    lg.addHandler(h)
    lg.addHandler(logging.StreamHandler())
    lg.info("Khởi động %s", APP_NAME)


def free_port(preferred: int = 8765) -> int:
    for p in [preferred, *range(preferred + 1, preferred + 50), 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if sys.platform != "win32":  # vừa tự khởi động lại: cổng cũ còn TIME_WAIT nhưng vẫn dùng lại được
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Không tìm được cổng trống")


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["cli"]:  # bản đóng gói: dùng CLI qua cùng file exe
        from videodubber.__main__ import main as cli_main
        sys.exit(cli_main(argv[1:]))
    ap = argparse.ArgumentParser(prog="videodubber-web", description=f"{APP_NAME} — giao diện web")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--token", help="Token cố định (mặc định ngẫu nhiên mỗi lần chạy)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 = mở cho máy khác trong mạng nội bộ (máy chủ dùng chung)")
    ap.add_argument("--allow-host", action="append", default=[],
                    help="Tên miền/IP mà người dùng gõ để vào (vd dubber.lutech.local hoặc 192.168.1.20). Lặp được.")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
    import uvicorn
    _setup_log()
    shared = a.host != "127.0.0.1"
    port = a.port if shared else free_port(a.port)
    token = a.token or secrets.token_urlsafe(24)
    STATE.port = port
    STATE.argv = argv
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    for h in a.allow_host:
        hosts |= {h, f"{h}:{port}"}
    if shared and not a.allow_host:
        print("Cảnh báo: chưa có --allow-host, máy khác sẽ bị chặn. Thêm --allow-host <IP hoặc tên máy chủ>.")
    app = create_app(token, hosts)
    shown = a.allow_host[0] if shared and a.allow_host else "127.0.0.1"
    url = f"http://{shown}:{port}/?t={token}"
    print(f"{APP_NAME} đang chạy: {url}\nĐóng cửa sổ này hoặc bấm Ctrl+C để thoát.", flush=True)
    if shared:
        print("Gửi link trên cho đồng nghiệp (link có mã truy cập — chỉ chia sẻ trong công ty).")
    if not a.no_browser and not shared:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=a.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
