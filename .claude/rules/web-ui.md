---
paths:
  - "web/static/**"
---
# Web UI

- Trước khi thiết kế/đổi giao diện cho khách: dùng skill `ui-ux-pro-max` để chọn style, palette, font; sau đó chạy skill `ui-review`.
- Alpine.js vendored (`web/static/vendor`). Không CDN, không build step, không inline `<script>`/`onclick` (CSP chặn).
- Màu/khoảng cách/bo góc chỉ dùng biến semantic trong `css/tokens.css`; không hard-code hex trong component.
  Mọi token phải có giá trị cho cả `[data-theme="dark"]`.
- Mọi chuỗi hiển thị qua `t('key')`, thêm key vào **cả** `i18n/vi.json` và `i18n/en.json`.
- A11y: control có label, `:focus-visible` rõ, vùng trạng thái `aria-live`, lỗi `role="alert"`, tương phản ≥ 4.5:1, vùng bấm ≥ 40px.
- Responsive từ 375px tới 1440px, không cuộn ngang. Tôn trọng `prefers-reduced-motion`.
- Đủ trạng thái: rỗng, đang tải/chạy, thành công, lỗi (có hướng dẫn sửa), bị vô hiệu (giải thích vì sao).
- Phần tử test bấm vào có `data-testid`.
- `localStorage` bọc try/catch, chỉ cho tiện ích cá nhân (ngôn ngữ, theme).
