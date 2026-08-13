# Lunch App

Ứng dụng nội bộ giúp một văn phòng nhỏ tổ chức đặt cơm trưa chung hằng ngày — thay cho việc nhắn tin/Excel thủ công. Bất kỳ nhân viên nào cũng có thể đứng ra rủ mọi người đặt chung cho một ngày, tự đặt trên Grab và thu tiền lại (mô hình "người phụ trách ngày" — không cố định vào một tài khoản quản trị).

## Tính năng chính

- **Đặt món theo ngày** — nhân viên chọn món từ thực đơn, đặt trước cho hôm sau nếu thực đơn đã lên sớm; giờ chốt đơn cố định 11:00 hằng ngày.
- **Người phụ trách ngày (Collector)** — ai thêm món đầu tiên cho một ngày thì tự nhận ngày đó; chỉ người này (và admin) mới sửa thực đơn/chốt đơn/xác nhận thanh toán cho đúng ngày đó.
- **Danh mục món theo nhà hàng** — nhập tên/giá một lần, các ngày sau chỉ cần tick chọn, không gõ lại; đổi giá gốc không ảnh hưởng ngược các ngày đã áp dụng trước đó.
- **Bảng điều khiển đơn** — tổng hợp theo món (để đặt Grab) và theo nhân viên (để thu tiền), gộp một chỗ.
- **Quỹ chung** — nạp/rút, trả đơn bằng quỹ, góp quỹ hàng tháng, sổ đối soát, chia phí ship.
- **Phân quyền theo vai trò** — Nhân viên / Thủ quỹ / Quản trị viên, một người có thể mang nhiều vai trò.
- **Trung tâm thông báo** — thông báo được lưu lại (không chỉ đẩy realtime rồi mất), chuông thông báo, đánh dấu đã đọc theo từng người xem.
- **Sổ ghi vết (audit log)** — ghi lại ai claim/gỡ một ngày, ai chốt đơn, ai xác nhận đã nhận tiền.
- **Realtime** — cập nhật trực tiếp qua Server-Sent Events, không cần tải lại trang.

## Kiến trúc & công nghệ

- **Backend**: Python (Flask 3), SQLite thuần (`sqlite3`, không ORM), kiến trúc phân lớp `api/` (route) → `services/` (nghiệp vụ, không phụ thuộc Flask) → `repositories/` (SQL) → `models/` (thực thể).
- **Frontend**: JavaScript ES module thuần, không framework, gọi REST API + lắng nghe SSE.
- **Migration**: Alembic (chỉ dùng làm runner chạy migration; mọi thay đổi schema mới nên tạo qua `alembic revision`, xem `backend/migrations/README`). Bootstrap schema ban đầu vẫn do `Database.init_schema()` tự lo, chạy mỗi lần app khởi động.
- **Test**: `pytest` cho backend.

## 3. Quy trình phát triển có hỗ trợ AI

Toàn bộ quá trình phát triển được thực hiện với **Claude Code**, sử dụng AI trực tiếp cho thiết kế, lập trình, kiểm thử và review.

Quy trình sử dụng:
- **Claude Code:** thực hiện phần lớn công việc phát triển.
- **3 nhóm chuyên biệt:** review độc lập theo từng góc nhìn.
- **AI Skills:** hỗ trợ review nhanh và tra cứu Design System.
- Các phát hiện quan trọng được kiểm chứng bằng test hoặc review lại trước khi áp dụng.

### Các Sub-Agent đã sử dụng

| STT | Agent | Mục đích sử dụng | Kết quả chính |
|---:|---|---|---|
| **1** | **Code Reviewer** | Rà soát toàn bộ diff chưa commit của mô hình Collector/Ownership và các thay đổi kiến trúc | Phát hiện lỗi lệch logic **"ngày hiện tại"** giữa frontend/backend và nguy cơ mất dữ liệu khi sửa món thiếu trường. Cả hai lỗi đã được sửa và kiểm chứng. |
| **2** | **Backend Architect** | - Review kiến trúc backend: layering, schema, phân quyền, service boundary.<br>- Triển khai các thay đổi về đa role, lịch coordinator, deadline, đặt lại đơn cũ, gộp đơn theo quán, chia phí ship và quỹ chung. | - Phát hiện **4 kiểu phân quyền** đang bị phân tán → gom thành bảng chính sách.<br>- Phát hiện thiếu **2 ràng buộc DB** cho bất biến nghiệp vụ.<br>- Tách logic báo cáo khỏi `OrderService` → `DashboardService`.<br>- Hoàn thành các thay đổi với **17/17 test pass** và **24/24 test pass**. |
| **3** | **Data Engineer** | Kiểm tra tầng dữ liệu, schema, migration và database development thực tế ở chế độ chỉ đọc | Phát hiện lỗi thực tế trong dữ liệu: trigger mới chặn sai việc sửa món khi dữ liệu cũ vi phạm điều kiện. Đã sửa ở cả **service** và **trigger**, đồng thời bổ sung regression test. |
| **4** | **UI Designer** | - Review toàn bộ giao diện sau khi đổi theme cam → xanh lá.<br>- Kiểm tra màu sắc, tương phản, phân cấp thông tin, component và layout.<br>- Review toàn bộ 9 trang để tìm lỗi căn chỉnh. | - Phát hiện **13 vấn đề** theo mức ưu tiên cao/vừa/thấp.<br>- Review lần 2 phát hiện thêm **8 vấn đề cụ thể theo file/line**.<br>- Kết quả được chuyển thành brief cho Frontend Developer. |
| **5** | **Frontend Developer** | - Sửa các lỗi UI/UX từ review.<br>- Chuẩn hóa badge, form, typography, icon, empty-state và spacing.<br>- Tinh chỉnh Design System trong `style.css`.<br>- Xử lý dark mode, transition, trạng thái `:active` và reduced-motion. | - Áp dụng trực tiếp các thay đổi vào CSS/HTML/JS.<br>- Sửa lỗi contrast trong dark mode.<br>- Bổ sung `--transition-fast` và `--transition-base`.<br>- Dọn code thừa.<br>- Phát hiện khoảng **20 file JS** sử dụng emoji làm icon → tách thành task riêng. |
| **6** | **AI Service Developer** | Dựng `ai_service.py` cho mã 7.7, làm tầng gọi LLM tập trung cho các tính năng AI về sau | **Chưa hoàn thành**. Agent bị dừng giữa chừng và không để lại code. |

### Các Skill đã sử dụng

| STT | Skill | Mục đích sử dụng | Kết quả |
|---:|---|---|---|
| **1** | `code-review` | Review nhanh git diff chưa commit ở backend và frontend, tập trung vào lỗi correctness và runtime rõ ràng | Phát hiện **6 lỗi thực tế**:<br>1. Thiếu authorization tại endpoint catalog.<br>2. Panel "Trả bằng quỹ" bị ẩn sai điều kiện.<br>3. Validation được kiểm tra trước authorization.<br>4. Endpoint `/deadline` bị mồ côi sau khi xóa UI.<br>5. `database.py` nuốt lỗi nhưng không ghi log như comment mô tả.<br>6. Guard không cần thiết trong `coordinator_routes.py` có thể vô hiệu hóa kiểm tra phân quyền broadcast. |
| **2** | `ui-ux-pro-max` | Tra cứu Design System cho dashboard/SaaS, màu sắc, typography, UX, motion và accessibility | - Đề xuất palette teal + cam và font Fira.<br>- Giữ lựa chọn thực tế của dự án: **xanh lá + Inter**.<br>- Cung cấp checklist **WCAG AA**.<br>- Đề xuất transition **150–300ms**, touch target và loại bỏ anti-pattern emoji-as-icon.<br>- Dùng kết quả làm cơ sở để tự triển khai CSS/HTML. |
| **3** | `Docx` | Tạo tài liệu Proposal Document phục vụ báo cáo và trình bày với mentor | Tạo `proposal.docx` gồm **5 phần**: tổng quan dự án, kiến trúc kỹ thuật, quy trình sử dụng AI, kết quả kiểm thử và định hướng phát triển tiếp theo. |

## Cấu trúc thư mục

```
lunch-app/
├── backend/
│   ├── lunchapp/
│   │   ├── api/            # Route Flask (blueprint), chỉ truyền actor xuống service
│   │   ├── services/       # Nghiệp vụ, Flask-agnostic
│   │   ├── repositories/   # Truy vấn SQL
│   │   ├── models/         # Thực thể
│   │   ├── core/           # Tiện ích dùng chung (auth, database, errors, dates...)
│   │   ├── config.py       # Cấu hình tập trung
│   │   └── container.py    # Nơi lắp ráp repository/service (dependency wiring)
│   ├── migrations/         # Alembic — thay đổi schema mới tạo ở đây
│   ├── tests/               # pytest
│   ├── run.py               # Điểm khởi chạy backend
│   └── requirements.txt
└── frontend/
    ├── js/
    │   ├── pages/           # Logic từng trang (Thực đơn, Đặt hàng, Quỹ, Cài đặt...)
    │   ├── components/      # Thành phần UI dùng lại
    │   └── core/             # ApiClient, Dom helper, realtime client...
    ├── assets/css/           # Style dùng chung
    └── *.html                # Mỗi trang một file HTML
```

## Chạy dự án

### Backend

```bash
cd backend
pip install -r requirements.txt
python run.py
```

Mặc định chạy tại `http://localhost:5000`. Lần chạy đầu tiên sẽ tự tạo `lunch.db` (SQLite) kèm dữ liệu mẫu.

### Frontend

```bash
cd frontend
python serve_no_cache.py 8080
```

Mở `http://localhost:8080`. Dùng server này thay vì `python -m http.server` để tránh trình duyệt cache JS/CSS cũ khi đang phát triển.

### Tài khoản mẫu (seed sẵn)

| Email | Mật khẩu | Vai trò |
|---|---|---|
| `admin@fpt.com` | `admin123` | Quản trị viên |
| `nhanvien@fpt.com` | `123456` | Nhân viên |

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LUNCH_APP_SECRET` | `change-this-secret-key` | Khoá bí mật cho session Flask — **bắt buộc đổi khi triển khai thật** |
| `LUNCH_EMAIL_DOMAINS` | `fpt.com` | Danh sách domain email được phép đăng ký, cách nhau bằng dấu phẩy |
| `GOOGLE_CLIENT_ID` | *(rỗng)* | Bật đăng nhập Google nếu có |
| `GRAB_FETCH_ENABLED` | `1` | Tự lấy đánh giá/địa chỉ quán khi dán link GrabFood (`0` để tắt) |

## Kiểm thử

```bash
cd backend
pytest -q
```

## Thay đổi cấu trúc database

Bootstrap ban đầu (`Database.init_schema()`) chạy tự động mỗi lần khởi động app và an toàn khi gọi lại nhiều lần. **Từ nay, thay đổi schema mới nên tạo qua Alembic** thay vì thêm vào `_migrate_columns()`:

```bash
cd backend
alembic revision -m "add whatever_column to whatever_table"
# điền upgrade()/downgrade() bằng SQL tay trong file migration vừa tạo
alembic upgrade head
```

Xem thêm chi tiết ở `backend/migrations/README`.
