"""Tự cập nhật ngay trong tool: kiểm tra bản mới trên GitHub Releases, tải về, thay bản đang chạy rồi tự mở lại.

Ba kiểu cài đặt, ba cách thay:
- Chạy từ mã nguồn: tải zip mã nguồn của tag mới, chép đè các file (giữ .venv, models, bin), cài thư viện mới nếu có,
  rồi khởi động lại chính tiến trình.
- App Windows (.exe): tải VideoDubber-windows.zip, giải nén ra thư mục tạm; file .exe đang chạy bị khoá nên một script
  .cmd nhỏ đợi tool tắt hẳn rồi chép đè và mở lại.
- App Mac (.app): tải VideoDubber-macos.zip, giải nén bằng `ditto` (giữ symlink + quyền chạy); script .sh đợi tool tắt,
  đổi bản .app cũ sang bản mới và mở lại.
Mở lại luôn dùng đúng cổng + mã truy cập cũ nên tab trình duyệt đang mở tự nối lại, không phải đăng nhập lại.
Dữ liệu người dùng (video, bản nháp, mô hình đã tải) nằm ở USER_DIR nên không bị đụng tới.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from . import defaults as D

REPO = os.environ.get("VIDEODUBBER_REPO", "dieuhoai/Video-Dubber")
APP = "VideoDubber"
KEEP = {".venv", "venv", "models", "bin", ".git", "dist", "build/out"}  # không chép đè khi cập nhật mã nguồn
log = logging.getLogger("videodubber")
Progress = Callable[[int, int], None]


class UpdateError(RuntimeError):
    """Lỗi có lời nhắn dễ hiểu để hiện thẳng lên giao diện."""


def api_url() -> str:
    return os.environ.get("VIDEODUBBER_UPDATE_URL") or f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", str(v).split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


# ---------------------------------------------------------------- kiểu cài đặt

def install_kind() -> str:
    """source | windows | macos | unsupported."""
    if not getattr(sys, "frozen", False):
        return "source"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "unsupported"


def install_target(kind: str | None = None) -> Path:
    """Thứ cần thay: thư mục mã nguồn, thư mục chứa VideoDubber.exe, hoặc gói VideoDubber.app."""
    kind = kind or install_kind()
    if kind == "source":
        return D.resource_root()
    exe = Path(sys.executable).resolve()
    if kind == "macos":
        return exe.parents[2]  # VideoDubber.app/Contents/MacOS/VideoDubber
    return exe.parent


def asset_name(kind: str) -> str | None:
    return {"windows": f"{APP}-windows.zip", "macos": f"{APP}-macos.zip"}.get(kind)


def blocker(kind: str | None = None) -> str | None:
    """Lý do không tự cập nhật được trên máy này (None = được)."""
    kind = kind or install_kind()
    if os.environ.get("VIDEODUBBER_NO_UPDATE"):
        return "Quản trị viên đã tắt tự cập nhật trên máy này."
    if kind == "unsupported":
        return "Bản này chưa hỗ trợ tự cập nhật — tải bản mới ở trang Releases."
    target = install_target(kind)
    if kind == "macos" and "AppTranslocation" in str(target):
        return ("macOS đang chạy app từ vị trí tạm nên không thay được. Kéo VideoDubber vào thư mục "
                "Ứng dụng (Applications), mở lại từ đó rồi bấm cập nhật.")
    probe = target.parent if kind == "macos" else target
    if not os.access(probe, os.W_OK):
        return f"Không có quyền ghi vào {probe} — chuyển tool sang thư mục của bạn (vd Desktop) rồi thử lại."
    return None


# ---------------------------------------------------------------- kiểm tra bản mới

@dataclass
class Release:
    version: str
    tag: str
    notes: str = ""
    url: str = ""          # trang release để xem chi tiết
    download: str = ""     # file cần tải cho máy này
    assets: dict[str, str] = field(default_factory=dict)


_cache: dict = {"at": 0.0, "rel": None}


def _get(url: str, timeout: float = 20, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept,
                                               "User-Agent": f"{APP}/{__version__}"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 — URL cố định của repo


def latest_release(force: bool = False, kind: str | None = None) -> Release:
    kind = kind or install_kind()
    if not force and _cache["rel"] and time.time() - _cache["at"] < 3600:
        return _cache["rel"]
    try:
        with _get(api_url()) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise UpdateError("Không kiểm tra được bản mới (mất mạng hoặc GitHub đang bận).") from e
    tag = str(data.get("tag_name") or "")
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in data.get("assets") or []}
    want = asset_name(kind)
    rel = Release(version=tag.lstrip("v"), tag=tag, notes=str(data.get("body") or "")[:4000],
                  url=str(data.get("html_url") or ""), assets=assets,
                  download=assets.get(want, "") if want else str(data.get("zipball_url") or ""))
    _cache.update(at=time.time(), rel=rel)
    return rel


def status(force: bool = False) -> dict:
    kind = install_kind()
    out: dict = {"current": __version__, "kind": kind, "available": False, "latest": None}
    try:
        rel = latest_release(force, kind)
    except UpdateError as e:
        out["error"] = str(e)
        return out
    out["latest"] = asdict(rel)
    out["available"] = is_newer(rel.version)
    out["blocked"] = blocker(kind) if out["available"] else None
    if out["available"] and not rel.download:
        out["blocked"] = "Bản mới đang được đóng gói trên GitHub — thử lại sau ít phút."
    return out


# ---------------------------------------------------------------- tải + chuẩn bị

def updates_dir() -> Path:
    return D.USER_DIR / "updates"


def download(url: str, dest: Path, on_progress: Progress | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        with _get(url, timeout=60, accept="*/*") as r, tmp.open("wb") as w:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1024 * 1024):
                w.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)
        tmp.replace(dest)
    except UpdateError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"Tải bản mới bị lỗi: {e}. Kiểm tra mạng rồi bấm lại.") from e
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for m in zf.infolist():
        p = (dest / m.filename).resolve()
        if root != p and root not in p.parents:
            raise UpdateError("File cập nhật không hợp lệ (đường dẫn lạ) — đã huỷ.")
    zf.extractall(dest)


def stage(kind: str, archive: Path, version: str, work: Path) -> Path:
    """Giải nén + kiểm tra file tải về đúng là bản cần cài. Trả về thư mục chứa bản mới."""
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    if kind == "macos":  # ditto giữ symlink + quyền chạy trong .app; zipfile của Python làm mất
        r = subprocess.run(["ditto", "-x", "-k", str(archive), str(work)], capture_output=True, text=True,
                           timeout=600)
        if r.returncode != 0:
            raise UpdateError(f"Giải nén bản mới lỗi: {r.stderr.strip()[-300:]}")
        if not (work / f"{APP}.app" / "Contents" / "MacOS" / APP).is_file():
            raise UpdateError("File tải về không phải bản app Mac — đã huỷ.")
        return work
    try:
        with zipfile.ZipFile(archive) as zf:
            _safe_extract(zf, work)
    except zipfile.BadZipFile as e:
        raise UpdateError("File tải về bị hỏng — bấm cập nhật lại.") from e
    if kind == "windows":
        if not (work / f"{APP}.exe").is_file():
            raise UpdateError("File tải về không phải bản app Windows — đã huỷ.")
        return work
    # Mã nguồn: zip của GitHub có 1 thư mục gốc (vd dieuhoai-Video-Dubber-abc123/).
    tops = [p for p in work.iterdir() if p.is_dir()]
    src = tops[0] if len(tops) == 1 and not (work / "videodubber").exists() else work
    init = src / "videodubber" / "__init__.py"
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8")) if init.is_file() else None
    if not m or parse_version(m.group(1)) != parse_version(version):
        raise UpdateError("File tải về không khớp phiên bản cần cài — đã huỷ.")
    return src


def _kept(rel: Path) -> bool:
    s = rel.as_posix()
    return any(s == k or s.startswith(k + "/") for k in KEEP)


def apply_source(src: Path, root: Path) -> list[str]:
    """Chép đè mã nguồn mới lên thư mục đang chạy (an toàn: file .py không bị khoá kể cả trên Windows)."""
    changed = []
    for f in src.rglob("*"):
        rel = f.relative_to(src)
        if f.is_dir() or _kept(rel) or "__pycache__" in rel.parts:
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".vdnew")
        shutil.copy2(f, tmp)
        os.replace(tmp, dest)
        changed.append(rel.as_posix())
    return changed


def missing_requirements(pyproject: Path) -> list[str]:
    """Thư viện bản mới cần mà môi trường hiện tại chưa có (chỉ xét tên, không xét phiên bản)."""
    from importlib import metadata
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    if not m:
        return []
    reqs = re.findall(r'"([^"]+)"', m.group(1))
    out = []
    for req in reqs:
        name = re.match(r"[A-Za-z0-9_.-]+", req)
        if not name:
            continue
        try:
            metadata.version(name.group(0))
        except metadata.PackageNotFoundError:
            out.append(req)
    return out


# ---------------------------------------------------------------- khởi động lại

def relaunch_args(argv: list[str], port: int, token: str) -> list[str]:
    """Giữ nguyên tham số người dùng chạy, ép đúng cổng + mã cũ để tab trình duyệt tự nối lại."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--port", "--token"):
            skip = True
            continue
        if a.startswith(("--port=", "--token=")) or a == "--no-browser":
            continue
        out.append(a)
    return [*out, "--port", str(port), "--token", token, "--no-browser"]


def _cmd_quote(s: str) -> str:
    return '"' + s.replace("%", "%%").replace('"', '""') + '"'


def windows_script(pid: int, stage_dir: Path, target: Path, launch: list[str], logf: Path) -> str:
    """Đợi tool tắt → chép đè thư mục app → mở lại. Lỗi chép thì vẫn mở lại bản cũ."""
    lg = _cmd_quote(str(logf))
    run = "start \"\" " + " ".join(_cmd_quote(a) for a in launch)
    return "\r\n".join([
        "@echo off",
        "chcp 65001 >nul",
        "set N=0",
        ":wait",
        f'tasklist /FI "PID eq {pid}" /NH 2>nul | findstr /R /C:" {pid} " >nul',
        "if errorlevel 1 goto copy",
        "set /a N+=1",
        "if %N% GEQ 120 goto copy",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":copy",
        f"robocopy {_cmd_quote(str(stage_dir))} {_cmd_quote(str(target))} /E /R:10 /W:1 /NFL /NDL /NP >> {lg} 2>&1",
        f"if %ERRORLEVEL% GEQ 8 (echo COPY FAILED >> {lg}) else (echo UPDATED >> {lg})",
        f"{run}",
        f"rmdir /s /q {_cmd_quote(str(stage_dir))} >nul 2>&1",
        "",
    ])


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def posix_script(pid: int, new_bundle: Path, target: Path, launch: list[str], logf: Path) -> str:
    """Đợi tool tắt → đổi gói .app cũ sang bản mới (hỏng thì trả lại bản cũ) → mở lại."""
    t, n, lg = _sh_quote(str(target)), _sh_quote(str(new_bundle)), _sh_quote(str(logf))
    old = _sh_quote(str(target) + ".old-update")
    return "\n".join([
        "#!/bin/sh",
        "i=0",
        f"while kill -0 {pid} 2>/dev/null && [ $i -lt 240 ]; do sleep 0.5; i=$((i+1)); done",
        f"rm -rf {old}",
        f"if mv {t} {old} && mv {n} {t}; then",
        f"  echo UPDATED >> {lg}; rm -rf {old}",
        "else",
        f"  echo SWAP FAILED >> {lg}; [ -e {t} ] || mv {old} {t}",
        "fi",
        f"xattr -dr com.apple.quarantine {t} 2>/dev/null",
        " ".join(_sh_quote(a) for a in launch) + f" >> {lg} 2>&1 &",
        "",
    ])


def spawn_detached(cmd: list[str]) -> None:
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                "close_fds": True}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)  # noqa: S603


def restart_source(root: Path, args: list[str]) -> None:
    """Khởi động lại tiến trình mã nguồn với mã mới. Mac/Linux: thay tại chỗ (giữ nguyên cửa sổ Terminal)."""
    cmd = [sys.executable, "-m", "web.server", *args]
    log.info("Khởi động lại sau cập nhật: %s", " ".join(cmd[:3]))
    os.chdir(root)
    if sys.platform == "win32":
        subprocess.Popen(cmd, cwd=root)  # noqa: S603 — dùng chung cửa sổ console
        os._exit(0)
    os.execv(sys.executable, cmd)


# ---------------------------------------------------------------- cả quy trình

def perform(rel: Release, args: list[str], on_stage: Callable[[str, int, int], None],
            kind: str | None = None, restart: bool = True) -> None:
    """Tải + cài bản mới. Chạy trong luồng nền; kết thúc bằng việc tự tắt và mở lại tool (restart=True)."""
    kind = kind or install_kind()
    why = blocker(kind)
    if why:
        raise UpdateError(why)
    if not rel.download:
        raise UpdateError("Bản mới chưa có file cho máy này — thử lại sau ít phút.")
    work = updates_dir() / rel.tag
    archive = download(rel.download, work.with_suffix(".zip"), lambda d, t: on_stage("download", d, t))
    on_stage("install", 0, 0)
    target = install_target(kind)
    logf = D.USER_DIR / "update.log"
    try:
        staged = stage(kind, archive, rel.version, work)
    finally:
        archive.unlink(missing_ok=True)
    log.info("Cập nhật %s → %s (%s, %s)", __version__, rel.version, kind, target)
    if kind == "source":
        apply_source(staged, target)
        shutil.rmtree(work, ignore_errors=True)
        need = missing_requirements(target / "pyproject.toml")
        if need:
            on_stage("libs", 0, 0)
            from .modelstore import pip_install
            pip_install(need)
        on_stage("restart", 0, 0)
        if restart:
            time.sleep(1.0)  # để trình duyệt nhận được trạng thái "đang khởi động lại"
            restart_source(target, args)
        return
    pid = os.getpid()
    if kind == "windows":
        script = updates_dir() / "update.cmd"
        script.write_text(windows_script(pid, staged, target, [str(target / f"{APP}.exe"), *args], logf),
                          encoding="utf-8")
        helper = ["cmd.exe", "/c", str(script)]
    else:
        script = updates_dir() / "update.sh"
        launch = ["open", "-n", str(target), "--args", *args]
        script.write_text(posix_script(pid, staged / f"{APP}.app", target, launch, logf), encoding="utf-8")
        helper = ["/bin/sh", str(script)]
    on_stage("restart", 0, 0)
    if restart:
        spawn_detached(helper)
        time.sleep(1.0)
        os._exit(0)
