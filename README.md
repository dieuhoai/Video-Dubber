# Video Dubber

Khung dự án cho **công cụ desktop chạy local**: lõi Python + CLI + giao diện web trong trình duyệt,
đóng gói thành `.exe` (Windows) và `.app` (macOS), phát hành qua GitHub Releases.


## Cài plugin Claude Code `lutech-tools`

Plugin gói quy trình làm tool thành các lệnh `/lutech-tools:*` dùng trong Claude Code / tab **Code** của Claude Desktop.

**Cần có:** [Claude Desktop](https://claude.com/download) hoặc Claude Code (lệnh `claude`), và [Python ≥ 3.10](https://www.python.org/downloads/)
(Windows: tích **"Add python.exe to PATH"** khi cài).

### Cách 1 — không dùng lệnh (non-tech)
1. Trên trang GitHub này bấm **Code → Download ZIP**, giải nén vào chỗ cố định, vd `Documents/lutech-tools`
   (**không xoá/di chuyển** thư mục sau khi cài — plugin chạy từ đó).
2. Double-click **`install.bat`** (Windows) hoặc **`install.command`** (macOS). Thấy **XONG** là được.
   macOS báo "nhà phát triển không xác định": chuột phải → **Open** → **Open**.
3. **Thoát hẳn Claude** (Windows: chuột phải icon ở khay đồng hồ → Quit; macOS: Cmd+Q) rồi mở lại.
4. Vào tab **Code**, gõ `/lutech-tools:help` để kiểm tra.

### Cách 2 — dòng lệnh
```bash
git clone https://github.com/codelord-commits/Lutech-Tools-Plugin.git lutech-tools
cd lutech-tools && ./install.sh
```
Cập nhật: `git pull && ./install.sh --update` · Gỡ: `./install.sh --uninstall`.

Hoặc ngay trong Claude Code:
```
/plugin marketplace add codelord-commits/Lutech-Tools-Plugin
/plugin install lutech-tools@lutech
```

### Dùng
- Không biết code: đọc [docs/HUONG-DAN.md](docs/HUONG-DAN.md), gõ `/lutech-tools:make-tool` + kể việc cần tự động hoá.
  Dân UA: xem thêm [docs/HUONG-DAN-UA.md](docs/HUONG-DAN-UA.md).
- Dev: `/lutech-tools:help`. Danh sách lệnh và hướng dẫn theo loại tool: [docs/PLUGIN.md](docs/PLUGIN.md).

## Dùng ngay (người dùng cuối)

1. Tải file zip cho hệ điều hành của bạn ở mục **Releases**.
2. Giải nén, mở `VideoDubber.exe` (Windows) hoặc `VideoDubber.app` (macOS).
3. Trình duyệt tự mở giao diện. Đóng cửa sổ dòng lệnh để thoát.

macOS chặn app chưa ký: chuột phải vào app → **Open** → **Open**.

## Chạy từ mã nguồn

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]
videodubber-web                          # giao diện web
videodubber run ./input ./output         # dòng lệnh
```

## Cấu trúc

```
videodubber/          lõi nghiệp vụ — thuần Python, không biết gì về web
  models.py        pydantic model, validate mọi input
  processor.py     nghiệp vụ chính (thay bằng của bạn)
  preset_io.py     preset built-in + của người dùng
  io_utils.py      ghi file nguyên tử, JSON UTF-8
  defaults.py      đường dẫn cấu hình theo OS, hỗ trợ PyInstaller
  __main__.py      CLI
web/               FastAPI server local + API + static UI (Alpine.js, không CDN)
presets/           preset mặc định đi kèm
tests/             unit / web (API) / ui (Playwright)
build/             PyInstaller spec + launcher (+ icon.ico / icon.icns)
scripts/           new_project, bump_version, check_privacy
docs/              LIFECYCLE, specs/, plans/, adr/, RELEASE
skills/            skill của plugin lutech-tools (/lutech-tools:*)
.claude-plugin/    manifest plugin + marketplace
.claude/           rule + hook cho Claude Code
.github/           CI test, release theo tag, template PR/issue
```

## Giấy phép

MIT — xem [LICENSE](LICENSE).
