"""Điểm vào của bản đóng gói: mở giao diện web; `<App> cli …` để dùng dòng lệnh."""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    conf = root / "fonts.conf"
    if conf.is_file():  # ffmpeg tĩnh trên macOS cần cấu hình để tìm font hệ thống (chữ Thái, Nhật…)
        os.environ.setdefault("FONTCONFIG_FILE", str(conf))

from web.server import main  # noqa: E402

if __name__ == "__main__":
    main()
