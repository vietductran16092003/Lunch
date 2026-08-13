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
