# Vòng đời dự án: từ ý tưởng đến release

Mỗi giai đoạn có **đầu vào**, **đầu ra (artifact)**, **cổng kiểm (gate)** và **skill Claude** tương ứng.
Không qua cổng thì không sang giai đoạn sau.

```
0 Khởi tạo → 1 Spec → 2 Thiết kế → 3 Plan → 4 Code (TDD) → 5 Review → 6 QA → 7 Release → 8 Bảo trì
```

| # | Giai đoạn | Artifact | Gate | Skill |
|---|-----------|----------|------|-------|
| 0 | Khởi tạo | repo từ template, `.privacy-blocklist` | `pytest -q` xanh trên repo mới | `new-tool` |
| 1 | Spec | `docs/specs/YYYY-MM-DD-<tên>.md` | Người dùng duyệt; không còn mục "Câu hỏi mở" | `spec-feature` |
| 2 | Thiết kế | mục Kiến trúc trong spec, ADR nếu có quyết định khó đảo ngược | Mỗi quyết định lớn có ADR | `spec-feature` |
| 3 | Plan | `docs/plans/YYYY-MM-DD-<tên>.md` | Mỗi task ≤ 1 commit, có test tương ứng | `plan-feature` |
| 4 | Code | code + test | Test viết trước và đã thấy đỏ; `pytest`, `ruff` xanh | `implement-tdd` |
| 5 | Review | ghi chú review | Không còn lỗi mức Cao; UI qua checklist | `review-change`, `ui-review` |
| 6 | QA | kết quả QA trong PR | Checklist QA đủ; test dữ liệu thật (nếu có) chạy local | `qa-check` |
| 7 | Release | tag `vX.Y.Z`, GitHub Release kèm zip | CI release xanh, tải zip về chạy thử được | `release` |
| 8 | Bảo trì | issue → fix → patch release | Lỗi có test tái hiện trước khi sửa | `implement-tdd` |

## 0. Khởi tạo
```bash
python scripts/new_project.py D:/Projects/my-tool --name "My Tool"
```
- Tạo `.privacy-blocklist` (không commit) chứa tên khách, tên app khách, domain nội bộ.
- Dữ liệu thật của khách để **ngoài repo**; test với dữ liệu thật qua biến `VIDEODUBBER_REAL_DATA`.

## 1. Spec — trả lời "làm gì, cho ai, thế nào là xong"
Dùng [specs/_TEMPLATE.md](specs/_TEMPLATE.md). Bắt buộc: người dùng mục tiêu, luồng chính, tiêu chí chấp nhận
đo được, edge case, ngoài phạm vi. Spec gốc của khách có thể chứa thông tin riêng → viết lại spec trung tính trong repo.

## 2. Thiết kế
- Ranh giới cứng: `videodubber/` (lõi) **không import** `web/`. Web và CLI là hai lớp vỏ mỏng gọi lõi.
- Quyết định khó đảo ngược (định dạng file, thư viện chính, cách đóng gói) → ADR theo [adr/_TEMPLATE.md](adr/_TEMPLATE.md).
- UI cho khách: áp dụng skill `ui-ux-pro-max` để chọn style/palette/font trước khi code.

## 3. Plan
Dùng [plans/_TEMPLATE.md](plans/_TEMPLATE.md): danh sách task nhỏ, mỗi task ghi file sẽ đụng, test sẽ viết, lệnh kiểm.

## 4. Code (TDD)
Đỏ → Xanh → Dọn. Không viết code nghiệp vụ khi chưa có test fail. Xem `.claude/rules/testing.md`.

## 5. Review
- Tự review diff (`/code-review`), rồi `/security-review` nếu đụng server/IO/subprocess.
- UI: checklist trong skill `ui-review` (a11y, responsive 375→1440, sáng/tối, vi/en, trạng thái rỗng/lỗi/đang chạy).

## 6. QA
Skill `qa-check`: chạy toàn bộ test, test UI, test dữ liệu thật (local), build thử PyInstaller, chạy file exe.

## 7. Release
Xem [RELEASE.md](RELEASE.md). Tóm tắt: `bump_version.py` → cập nhật CHANGELOG → commit → tag `vX.Y.Z` → push tag →
GitHub Actions build Windows/macOS và đính kèm zip vào Release.

## 8. Bảo trì
Issue → test tái hiện (đỏ) → sửa → patch release. Phụ thuộc: xem lại mỗi quý (`pip list --outdated`).
