# Bảo mật

Tool chạy hoàn toàn trên máy người dùng:

- Server chỉ nghe `127.0.0.1`, cổng ngẫu nhiên nếu bận.
- Mỗi lần chạy sinh token ngẫu nhiên; token trên URL được đổi thành cookie `HttpOnly; SameSite=Strict` rồi xoá khỏi URL.
- Kiểm tra `Host`/`Origin` chống DNS-rebinding và CSRF; CSP `default-src 'self'`, không tải gì từ CDN lúc chạy.
- Không gửi dữ liệu ra ngoài, không telemetry.

Báo lỗ hổng: mở GitHub Security Advisory riêng tư (không mở issue công khai).
