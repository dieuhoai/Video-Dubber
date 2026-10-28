# Video Dubber

**Nhân bản video quảng cáo sang nhiều ngôn ngữ và nhiều câu hook:** đưa vào 1 video đang win, nhận về hàng loạt video
đã đổi caption + giọng đọc, giữ nguyên hình, nhịp cắt và nhạc nền.

```
1 video gốc  ×  (ngôn ngữ × câu hook)  →  N video MP4  +  kiểm tra tự động
   es: 3 câu hook, de: 2 câu hook       →  5 video: bdaycard_hookIA_es_f1_h1_9x16_v1.mp4 …
```

## Tải về và mở (không cần cài gì)

1. Vào trang **[Releases](../../releases/latest)**, tải `VideoDubber-windows.zip` (máy Mac chip Apple: `VideoDubber-macos.zip`).
2. **Giải nén** (chuột phải → *Extract All…*) vào chỗ cố định, vd `D:\VideoDubber`. Đừng chạy thẳng trong file zip.
3. Nhấp đúp **`VideoDubber.exe`** → cửa sổ đen hiện ra, trình duyệt tự mở giao diện. **Đừng đóng cửa sổ đen** khi đang dùng.
   - Windows báo *"Windows protected your PC"*: bấm **More info → Run anyway** (tool chưa mua chữ ký số, không phải virus).
   - Mac: lần đầu macOS chặn → **Cài đặt hệ thống → Quyền riêng tư & Bảo mật → Vẫn mở**. Bản Mac chạy ngầm, không có cửa sổ đen; muốn tắt: chuột phải biểu tượng trên Dock → Thoát.
4. **Cập nhật:** khi có bản mới, đầu trang tool hiện **Cập nhật ngay** — bấm là xong, tool tự tải, cài và mở lại (không cần tải lại từ GitHub). Mac: để app trong thư mục *Ứng dụng* (Applications) thì mới tự cập nhật được.
5. App đã có sẵn giọng đọc offline + tách nhạc, chạy không cần Internet (trừ các ngôn ngữ dùng giọng Microsoft).

## Cách dùng (4 bước trên giao diện web)

1. **Video gốc** — tải MP4 lên. Nhập caption gốc (giây bắt đầu/kết thúc + chữ), kiểm tra khung đỏ trùng vùng caption cũ,
   bấm **Xem thử caption mới**. Chọn âm thanh:
   - *Giữ âm gốc* — chỉ đổi chữ.
   - *Tách nhạc, đọc voice mới* — tool tự bỏ giọng gốc, giữ nhạc nền, rồi đọc lời mới. Nhập script gốc theo mốc giây.
2. **Ngôn ngữ** — tick ngôn ngữ, chọn giọng nữ/nam.
3. **Text & lời thoại** — mỗi dòng trong ô *Câu hook* = 1 video. Tick *Câu thoại 1 đọc đúng câu hook* để chữ và giọng khớp.
   Không tự dịch? Bấm **Copy prompt để dán vào Claude**, dán câu trả lời vào ô bên dưới → **Điền vào các ô**.
4. **Kết quả** — xem từng video, đọc huy hiệu kiểm tra (thời lượng, tốc độ voice, chữ vừa khung, font, âm lượng −14 LUFS,
   glossary), tải từng file hoặc **Tải tất cả (ZIP)**.

## Cài trên máy chủ nội bộ (dùng chung cho team)

Cần: Python ≥ 3.10, [FFmpeg](https://ffmpeg.org/download.html) (có libass — bản build phổ biến đều có),
font Noto cho Thái/Ả Rập/Nhật/Hàn/Trung/Hindi (Ubuntu: `sudo apt install fonts-noto-core fonts-noto-cjk`).

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python scripts/get_models.py          # tải mô hình tách nhạc + giọng offline (~420 MB, 1 lần)
.venv/bin/python -m web.server --host 0.0.0.0 --port 8765 --allow-host 192.168.1.20 --token <mã-bí-mật>
```

Server in ra link `http://192.168.1.20:8765/?t=<mã>` — gửi link này cho team (chỉ chia sẻ trong công ty).
Dữ liệu (video gốc, kết quả) nằm ở `VIDEODUBBER_DATA` (mặc định `~/.config/videodubber/data`).

Chạy trên máy cá nhân: bỏ `--host/--allow-host`, trình duyệt tự mở.

### Giọng đọc

| Cấu hình | Giọng | Ghi chú |
|---|---|---|
| mặc định (`auto`) | Kokoro offline cho es, fr, en, it, pt-BR, ja, zh, hi; còn lại Microsoft Edge TTS | Edge cần Internet |
| `VIDEODUBBER_TTS=edge` | Microsoft Edge TTS mọi ngôn ngữ | miễn phí, cần Internet |
| `VIDEODUBBER_TTS=espeak` | espeak-ng | giọng máy, chỉ để thử |

Dịch tự động bằng Claude API: đặt `ANTHROPIC_API_KEY` trên máy chủ → hiện nút **Dịch tự động** ở bước 3.

### Dòng lệnh

```bash
videodubber langs                         # ngôn ngữ + giọng
videodubber new video.mp4 --name "Bday"   # tạo template → in mã
videodubber show <mã> > t.json            # sửa t.json rồi:
videodubber update <mã> t.json
videodubber render batch.json             # {"template_id": "...", "variants": [{"lang": "es", "hook": "h1", "captions": [...], "voice": [...]}]}
```

## Phát triển

```bash
.venv/bin/pip install -e .[dev]
.venv/bin/python -m pytest -q        # unit + pipeline thật với ffmpeg + API + giao diện (Playwright)
.venv/bin/ruff check .
```

Spec: [docs/specs/2026-10-22-video-dubber-mvp.md](docs/specs/2026-10-22-video-dubber-mvp.md).
Font caption Fredoka (SIL OFL, `fonts/OFL-Fredoka.txt`). Mô hình: UVR MDX-Net Inst HQ 3, Kokoro v1.0 (tải riêng, xem giấy phép gốc).
