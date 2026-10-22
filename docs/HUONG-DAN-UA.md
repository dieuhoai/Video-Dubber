# Dùng AI cho công việc UA — hướng dẫn theo tình huống

Tài liệu cho UA/PO không biết code. Mỗi tình huống ghi: **dùng gì**, **làm thế nào**, **lưu ý**.
Cài đặt plugin xem [HUONG-DAN.md](HUONG-DAN.md).

## 0. Chọn đúng công cụ

| Việc của bạn | Dùng |
|--------------|------|
| Đã có file (export từ Adjust, network, SocialPeta…) → cần gộp, so sánh, làm báo cáo | `/lutech-tools:make-tool` — làm 1 lần, bấm chạy mãi |
| Cần **tự động theo giờ/ngày** + **báo tin** (camp tiêu bất thường, matchrate giảm, trend…) | **Scheduled task** của Claude + **connector (MCP)** tới nguồn dữ liệu |
| Hỏi/research một lần | Chat bình thường, theo cách hỏi ở mục 1 |

> Tool làm bằng `make-tool` chạy trên máy bạn, **chỉ chạy khi bạn bấm** và mặc định không lên mạng.
> Nó hợp với việc xử lý file, không hợp với việc canh số liên tục.

## 1. Cách hỏi AI để không bị "bịa"

1. **Đưa dữ liệu thật, đừng bắt AI nhớ.** Dán/đính kèm file report, ảnh chụp dashboard, link nguồn. AI bịa chủ yếu khi phải tự nghĩ ra số.
2. **Nói rõ 4 thứ:** bối cảnh (dự án, kênh, thị trường) · việc cần làm · định dạng kết quả (bảng cột gì) · tiêu chí đúng.
   > Vd: "Đây là report Adjust 7 ngày (file đính kèm). Lập bảng theo country: cost, revenue, ROAS D0, CPI. Đánh dấu đỏ country có ROAS < 80%. Chỉ dùng số trong file, thiếu số thì ghi 'không có'."
3. **Bắt AI trích nguồn:** "Mỗi kết luận ghi rõ lấy từ dòng/cột nào / link nào." Không trích được → đừng tin.
4. **Cho AI quyền nói "không biết":** "Nếu không chắc, nói không chắc và hỏi lại tôi."
5. **Kiểm chéo 2–3 con số** với dashboard gốc trước khi dùng kết quả. Lĩnh vực mình không rành → nhờ AI giải thích cách nó tính, rồi hỏi người trong ngành.
6. **Hỏi từng bước:** hiểu vấn đề → đề xuất cách làm → mình duyệt → mới làm. Đừng yêu cầu "làm hết" một lần.

## 2. Từ ý tưởng đến tool (quy trình `make-tool`)

1. Gõ `/lutech-tools:make-tool` + kể việc đang làm tay, càng cụ thể càng tốt (file đầu vào là gì, kết quả mong muốn trông ra sao).
2. Claude hỏi lại vài câu → **trả lời bằng ví dụ thật** (đính kèm 1 file mẫu đã xoá thông tin nhạy cảm).
3. Claude cho xem **bản mô phỏng** giao diện/bảng kết quả → sửa đến khi đúng ý rồi mới cho làm.
4. Nhận tool → chạy thử với dữ liệu thật → sai chỗ nào dùng `/lutech-tools:fix-tool` + mô tả ("cột ROAS đang chia sai", "thêm cột LTV D7").
5. Dùng ổn → `/lutech-tools:package-tool` để gửi đồng nghiệp.

**Skill** = một bộ hướng dẫn cố định để AI làm một việc lặp lại giống nhau mỗi lần (vd "quy trình check camp sáng thứ Hai").
Cách tạo: làm việc đó cùng Claude vài lần cho chuẩn → nói "đóng gói quy trình này thành skill". Nhờ team kỹ thuật thêm vào plugin nếu muốn dùng chung.

## 3. Tình huống cụ thể

### Báo cáo tuần/tháng theo bộ creative × network
- **Dùng:** `make-tool`.
- **Cách:** export report từng network + Adjust ra CSV/Excel vào một thư mục → tool gộp thành 1 file: cost, revenue, ROAS, CPI, LTV theo bộ CRT, từng CRT, từng network; đánh dấu bộ win/fail theo ngưỡng bạn đặt.
- **Lưu ý:** đặt tên creative theo quy ước thống nhất (ngách_kịch bản_ngôn ngữ…) thì tool mới tách được theo ngách.

### Research đối thủ / sản phẩm mới (SocialPeta, AppStore spy, Sensor Tower)
- **Dùng:** `make-tool` cho phần gộp; Chat cho phần phân tích.
- **Cách:** export danh sách từ từng nguồn → tool gộp về 1 sheet theo mẫu có sẵn (tên app, link creative YouTube, ngày, thị trường…). Sau đó đưa sheet cho Claude tóm tắt điểm chung, hướng đang win.
- **Lưu ý:** tự lấy dữ liệu trực tiếp từ các trang này cần tài khoản/API, thường vi phạm điều khoản nếu dùng scraping — hỏi team kỹ thuật trước.

### Cảnh báo camp tiêu đột biến, ROAS thấp, sắp hết budget (Google Ads)
### Cảnh báo matchrate / CTR giảm bất thường trong ngày
### Theo dõi CPI/LTV theo khung giờ và theo thị trường
- **Dùng:** scheduled task của Claude + connector tới Google Ads / Adjust + kênh báo tin (Slack/email).
- **Cách:**
  1. Nhờ team kỹ thuật kết nối connector cho nguồn dữ liệu (Google Ads, Adjust…). **Không tự dán API key vào chat.**
  2. Thử tay trước trong Chat: "Kéo spend và ROAS theo giờ hôm nay của các camp dự án X, so với trung bình 7 ngày cùng giờ" — kiểm số khớp dashboard.
  3. Viết rõ **luật cảnh báo** bằng con số: "spend giờ này > 2× trung bình giờ VÀ ROAS < 70%", "đã tiêu > 85% budget trước 18h", "matchrate giảm > 20% so với cùng giờ hôm qua".
  4. Khi đã đúng: "Tạo scheduled task chạy mỗi giờ từ 8h–23h, check theo luật trên, có vi phạm thì gửi tin vào kênh Slack #ua-alert".
- **Lưu ý:** dữ liệu Adjust/network có độ trễ — chọn giờ check sau giờ cập nhật số. Bắt đầu với ít luật, chỉnh ngưỡng sau 1 tuần để tránh báo nhiễu. Matchrate: xác định trước lấy từ nguồn nào (Adjust hay mediation), nếu chưa có API thì chưa tự động được.

### Tổng hợp trend theo country hằng ngày
- **Dùng:** scheduled task + tìm kiếm web của Claude.
- **Cách:** "Mỗi sáng 8h, tìm chủ đề đang/sắp hot ở US, BR, IN (phim sắp chiếu, giải đấu, sự kiện) từ Google Trends, TikTok Creative Center, tin tức; liệt kê 5 chủ đề/country kèm link nguồn và ngày diễn ra; gửi vào Slack."
- **Lưu ý:** luôn bắt kèm link nguồn và mở kiểm vài link — trend AI tự nêu mà không có link là dấu hiệu bịa.

## 4. Không bao giờ
- Dán API key, mật khẩu, token tài khoản quảng cáo vào chat.
- Gửi file có dữ liệu doanh thu dự án cho công cụ AI ngoài danh sách công ty cho phép.
- Ra quyết định tăng/giảm budget chỉ dựa trên số AI báo mà không mở dashboard kiểm lại.
