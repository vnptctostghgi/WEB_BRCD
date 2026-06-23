# BRCĐ Admin - Bước 1

Ứng dụng mẫu quản trị Băng rộng cố định, dùng Python/FastAPI và kiến trúc 3 lớp.

## Mô hình 3 lớp hoạt động thế nào?

1. **Presentation Layer** (`app/presentation`): hiển thị trang web, nhận thao tác bấm nút và trả JSON cho trình duyệt.
2. **Application Layer** (`app/application`): điều phối nghiệp vụ, quyết định thông báo nào an toàn để trả về giao diện.
3. **Data Access Layer** (`app/data_access`): lớp duy nhất được phép trực tiếp kết nối và chạy câu lệnh với Oracle.

Khi bạn bấm **Kiểm tra kết nối**, trình duyệt gọi `GET /api/health/database`. Route chuyển yêu cầu cho `DatabaseService`, service gọi `OracleRepository`, repository kết nối Oracle và chạy một câu `SELECT`.

## 1. Công cụ cần cài

- Python 3.12 hoặc 3.13.
- Visual Studio Code (khuyên dùng, nhưng không bắt buộc).
- Thông tin Oracle do đơn vị cấp: host/IP, port, Service Name, username, password.
- Kết nối mạng nội bộ hoặc VPN có thể đi tới máy chủ Oracle.

Không cần Node.js, React hay Oracle Instant Client ở bước này. Thư viện `python-oracledb` chạy ở **Thin mode** mặc định.

## 2. Tạo môi trường Python riêng

Mở PowerShell tại thư mục dự án và chạy từng lệnh:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

- `python -m venv .venv`: tạo một môi trường Python riêng trong thư mục `.venv`.
- `Activate.ps1`: kích hoạt môi trường đó.
- `pip install`: cài đúng các thư viện và phiên bản trong `requirements.txt`.

## 3. Chạy thử chưa cần Oracle thật

```powershell
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000`, bấm **Kiểm tra kết nối**. Nếu thấy chế độ `mock`, toàn bộ luồng 3 lớp đã hoạt động.

Bạn cũng có thể mở `http://127.0.0.1:8000/docs` để thử API trực tiếp.

## 4. Kết nối Oracle thật

Mở file `.env` và thay:

```dotenv
DB_MOCK_MODE=false
DB_HOST=dia-chi-ip-hoac-hostname
DB_PORT=1521
DB_SERVICE=service-name-do-don-vi-cap
DB_USER=tai-khoan-cua-ban
DB_PASS=mat-khau-cua-ban
```

Khởi động lại ứng dụng, rồi bấm **Kiểm tra kết nối**.

### Giải thích phần kết nối

Trong `app/data_access/oracle_repository.py`:

- `oracledb.makedsn(...)` tạo địa chỉ kết nối từ host, port và Service Name.
- `oracledb.connect(...)` mở kết nối bằng tài khoản chỉ đọc.
- `with ... as connection` tự đóng kết nối kể cả khi xảy ra lỗi.
- `cursor.execute(...)` chạy câu `SELECT SYSDATE AS SERVER_TIME FROM DUAL`.
- Mật khẩu được đọc từ `.env` ở Backend, không xuất hiện trong HTML hoặc JavaScript.

## 5. Cách kiểm tra khi kết nối lỗi

Trong PowerShell:

```powershell
Test-NetConnection YOUR_ORACLE_HOST -Port 1521
```

- `TcpTestSucceeded: True`: máy của bạn đi được tới cổng Oracle.
- `False`: cần bật VPN, kiểm tra firewall hoặc hỏi quản trị Database.

Các nguyên nhân thường gặp:

- Sai **Service Name** hoặc nhầm Service Name với SID.
- Chưa kết nối mạng nội bộ/VPN.
- Tài khoản hết hạn, bị khóa hoặc sai mật khẩu.
- Máy chủ Oracle không cho phép IP máy bạn kết nối.

## 6. Quy tắc bảo mật bắt buộc

- Không viết username/password trực tiếp trong code.
- Không gửi mật khẩu Oracle xuống trình duyệt.
- Không commit file `.env`; `.gitignore` đã chặn file này.
- Chỉ dùng tài khoản có quyền `SELECT` trên đúng view/table cần thiết.
- Khi public cho nhiều người: mỗi người đăng nhập bằng tài khoản ứng dụng; Backend dùng một tài khoản Oracle dịch vụ có quyền tối thiểu. Không chia sẻ tài khoản Oracle cho người dùng cuối.
- Không public Backend miễn phí trên Internet nếu Oracle chỉ truy cập qua mạng nội bộ. Hãy chạy Backend trong mạng đơn vị hoặc qua hạ tầng/VPN được đơn vị phê duyệt.

## 7. Chạy kiểm thử tự động

```powershell
python -m pytest
```

Hai bài test xác nhận trang chủ tải được và API kiểm tra Database đi qua mock mode thành công.

## 8. Đọc code theo thứ tự dành cho người mới

### `app/main.py` - điểm bắt đầu

```python
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/presentation/static"), name="static")
app.include_router(router)
```

- `get_settings()` đọc cấu hình từ `.env`.
- `FastAPI(...)` tạo ứng dụng Backend.
- `app.mount(...)` cho phép trình duyệt tải CSS và JavaScript.
- `app.include_router(router)` gắn các đường dẫn `/` và `/api/health/database` vào ứng dụng.

### `app/presentation/routes.py` - lớp giao diện

```python
@router.get("/api/health/database")
def database_health() -> dict:
    return build_database_service().get_connection_status()
```

- `@router.get(...)` khai báo một API dùng phương thức HTTP GET.
- Khi trình duyệt gọi API, hàm `database_health()` chạy.
- Hàm không tự kết nối Oracle; nó chuyển việc đó cho Application Layer.

### `app/application/database_service.py` - lớp xử lý

```python
details = self.repository.check_connection()
return {"ok": True, "message": "Kết nối Database thành công.", "details": details}
```

- Service gọi repository để kiểm tra kết nối.
- Nếu thành công, service chuẩn hóa kết quả để giao diện dễ sử dụng.
- Nếu Oracle báo lỗi, service ghi chi tiết vào log Backend nhưng chỉ trả thông báo chung ra trình duyệt. Việc này tránh lộ cấu hình nội bộ.

### `app/data_access/oracle_repository.py` - lớp truy cập dữ liệu

```python
dsn = oracledb.makedsn(host, port, service_name=service_name)
with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT SYSDATE AS SERVER_TIME FROM DUAL")
        database_time = cursor.fetchone()[0]
```

- `makedsn(...)` ghép địa chỉ Oracle.
- `connect(...)` mở kết nối. Mật khẩu chỉ tồn tại ở Backend.
- `cursor()` tạo đối tượng chạy SQL.
- Câu SQL được cố định là `SELECT`, không lấy từ người dùng.
- `fetchone()` đọc một dòng kết quả.
- Hai khối `with` tự đóng cursor và connection.

### `app/presentation/static/app.js` - thao tác nút bấm

```javascript
const response = await fetch("/api/health/database");
const data = await response.json();
```

- `fetch(...)` gọi API Backend.
- `await` chờ Backend trả lời mà không làm treo trang.
- `response.json()` chuyển kết quả JSON thành dữ liệu JavaScript để hiển thị.

## 9. Lộ trình sau Bước 1

1. **Bước 2 - Đọc dữ liệu BRCĐ:** xác định view/table được phép đọc, tạo API danh sách có phân trang và tìm kiếm.
2. **Bước 3 - Dashboard:** thêm chỉ số tổng hợp, biểu đồ và bộ lọc địa bàn/thời gian.
3. **Bước 4 - Đăng nhập:** tạo tài khoản ứng dụng riêng, phân quyền quản trị viên/người xem; không dùng tài khoản Oracle để người dùng đăng nhập.
4. **Bước 5 - Triển khai nội bộ:** đặt Backend trong mạng có thể truy cập Oracle; Frontend có thể tách ra hosting tĩnh khi cần.
5. **Bước 6 - Mở rộng:** dùng Oracle connection pool, audit log, HTTPS, quản lý secret tập trung và kiểm thử tải.

## 10. Font chữ và Responsive

Giao diện dùng font **Be Vietnam Pro** từ Google Fonts vì dễ đọc và hỗ trợ đầy đủ tiếng Việt. Trong `styles.css`, font có chuỗi dự phòng:

```css
font-family: "Be Vietnam Pro", Inter, "Segoe UI", Arial, sans-serif;
```

Nếu không tải được Google Fonts, trình duyệt tự dùng font sans-serif có sẵn trên máy.

### Cỡ chữ và khoảng cách dòng

Các cỡ chữ được khai báo một lần bằng CSS variables:

```css
--text-sm: 0.8125rem;
--text-base: 0.9375rem;
--text-lg: 1.125rem;
--text-xl: clamp(1.25rem, 2vw, 1.5rem);
--text-hero: clamp(1.8rem, 4vw, 2.625rem);
--reading-line: 1.65;
--compact-line: 1.35;
```

- Nội dung báo cáo dùng khoảng `14-16px` và `line-height: 1.5-1.65`.
- Tiêu đề dùng line-height thấp hơn, khoảng `1.25-1.35`.
- `rem` giúp cỡ chữ thay đổi theo thiết lập trợ năng của trình duyệt.
- `clamp()` giúp tiêu đề tự co giãn giữa điện thoại và máy tính.

### Flexbox, Grid và breakpoint

- Flexbox dùng cho các hàng như logo, tiêu đề và nút.
- CSS Grid dùng cho thẻ chỉ số và luồng xử lý.
- Giao diện được viết theo hướng mobile-first. CSS mặc định dành cho điện thoại; các breakpoint `680px` và `981px` mở rộng bố cục cho tablet và PC.
- Không cần viết một trang HTML riêng cho từng thiết bị.

### Bảng rộng trên điện thoại

Luôn bọc bảng số liệu bằng:

```html
<div class="table-scroll" tabindex="0">
  <table>...</table>
</div>
```

Và dùng:

```css
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

table {
  min-width: 780px;
}
```

Bảng giữ được độ rộng cần thiết, còn người dùng điện thoại có thể vuốt ngang mượt mà. Nút và menu có chiều cao tối thiểu `46-48px`, phù hợp thao tác bằng ngón tay.

## 11. Đăng nhập và quản trị hệ thống

Ứng dụng dùng hai Database tách biệt:

- **Oracle**: chỉ đọc dữ liệu nghiệp vụ để làm báo cáo.
- **SQLite `data/app.db`**: lưu tài khoản ứng dụng và nhật ký hoạt động.

### Tài khoản khởi tạo

Sau lần chạy đầu tiên, đăng nhập bằng thông tin trong `.env`:

```dotenv
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=Admin@Brcd2026!
```

Hệ thống sẽ yêu cầu đổi mật khẩu. Sau khi tài khoản admin đã được tạo trong SQLite, thay đổi `INITIAL_ADMIN_PASSWORD` không tự đổi mật khẩu hiện tại.

### Chức năng đã có

- Đăng nhập, đăng xuất và phiên đăng nhập 8 giờ.
- Mật khẩu băm bằng `scrypt`, không lưu mật khẩu rõ.
- Vai trò `admin` và `viewer`.
- Admin tạo, sửa, khóa/mở tài khoản và đặt lại mật khẩu.
- Người dùng tự đổi mật khẩu.
- Nhật ký đăng nhập và thao tác quản trị.
- Trang kiểm tra trạng thái hệ thống và Oracle.
- Chặn người chưa đăng nhập và người không có quyền ở cả giao diện lẫn API.

### Chạy hệ thống

```powershell
cd D:\DEV\WEB
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000`. Không chia sẻ file `.env` hoặc thư mục `data` lên Internet.

## 12. Kho tài khoản website và cây quyền

- Admin quản lý **Danh mục website** gồm tên, địa chỉ, trạng thái và cờ yêu cầu OTP.
- Người dùng chọn tên website; giao diện tự điền địa chỉ và thông báo OTP.
- Tài khoản website thuộc riêng từng người dùng.
- Mật khẩu website được mã hóa bằng khóa ứng dụng trước khi lưu vào SQLite.
- API danh sách không trả mật khẩu hoặc chuỗi mã hóa.
- Chỉ giải mã khi người dùng có quyền `xemmatkhaudaluu` bấm **Xem mật khẩu**; thao tác này được ghi audit log.
- Admin cấp quyền theo cây trong màn hình **Quản trị người dùng**.

Cây chức năng hiện có:

```text
Tổng quan
Kho tài khoản web
  Xem danh sách tài khoản
  Thêm và sửa tài khoản
  Xem mật khẩu đã lưu
Quản trị
  Quản trị người dùng
  Quản trị danh mục website
  Phân quyền chức năng
  Xem nhật ký hoạt động
```

Khi phát sinh danh mục mới, tạo bảng danh mục riêng trong `AppRepository`, API admin tương ứng và thêm mã chức năng vào bảng `features`.

Khóa mã hóa kho tài khoản được dẫn xuất từ `SESSION_SECRET`. Phải sao lưu bí mật này an toàn; nếu đổi hoặc làm mất `SESSION_SECRET`, các mật khẩu website đã lưu sẽ không thể giải mã.

## 12.1. Quản trị kết nối hệ thống

Phân hệ **Quản trị hệ thống** có thêm danh mục kết nối:

- `DB cơ quan Oracle`: dùng biến `.env` `DB_HOST`, `DB_PORT`, `DB_SERVICE`, `DB_USER`, `DB_PASS`.
- `DB của web Supabase`: dùng `SUPABASE_REST_URL` và `SUPABASE_SECRET_KEY`.
- `FTP`: placeholder, chưa cấu hình server/user/password.
- `Drive`: placeholder, chưa cấu hình OAuth/service account.

API không trả mật khẩu hoặc secret ra giao diện; chỉ hiển thị `secret_ref` để biết secret đang nằm ở biến môi trường nào.

Kết nối đã seed trên Supabase:

```text
oracle_agency_db  -> DB cơ quan Oracle    -> kiểm tra thành công
supabase_web_db   -> DB của web Supabase  -> kiểm tra thành công
ftp_storage       -> FTP                  -> chưa cấu hình
drive_storage     -> Drive                -> chưa cấu hình
telegram_bot      -> Telegram Bot cảnh báo -> gửi cảnh báo lỗi hệ thống
```

Nếu Supabase đã có schema cũ, chạy thêm [supabase_connections_patch.sql](D:/DEV/WEB/supabase_connections_patch.sql) để tạo bảng `system_connections` và quyền mới.

## 12.2. Cảnh báo Telegram

Cấu hình trong `.env`:

```dotenv
TELEGRAM_TOKEN=...
MY_TELEGRAM_ID=...
BOT_USERNAME=@ten_bot
```

Backend sẽ gửi Telegram khi:

- Kiểm tra DB cơ quan Oracle thất bại.
- Kiểm tra kết nối hệ thống thất bại.
- Web phát sinh lỗi chưa xử lý.

Token bot chỉ được dùng ở Backend. Nếu token đã từng gửi qua chat hoặc lộ ra ngoài, hãy rotate token trong BotFather.

## 13. Chuyển Database chính sang Supabase

Ứng dụng đã có sẵn hai backend lưu trữ:

- `sqlite`: chạy cục bộ bằng `data/app.db`.
- `supabase`: dùng Supabase REST/PostgREST làm Database chính.

### Bước chuyển sang Supabase

1. Mở Supabase Dashboard > SQL Editor.
2. Chạy toàn bộ file [sql/supabase_schema.sql](sql/supabase_schema.sql).
3. Kiểm tra lại `.env`:

```dotenv
APP_DATABASE_BACKEND=supabase
SUPABASE_REST_URL=https://your-project.supabase.co/rest/v1
SUPABASE_SECRET_KEY=...
```

4. Khởi động lại ứng dụng:

```powershell
python -m uvicorn app.main:app --reload
```

5. Đăng nhập bằng `INITIAL_ADMIN_USERNAME` và `INITIAL_ADMIN_PASSWORD` nếu Supabase chưa có user admin.

### Chuyển dữ liệu hiện có từ SQLite sang Supabase

Sau khi chạy `supabase_schema.sql`, nếu muốn đưa user/danh mục/quyền hiện có lên Supabase:

```powershell
cd D:\DEV\WEB
.\.venv\Scripts\Activate.ps1
python scripts\migrate_sqlite_to_supabase.py
```

Sau khi migrate thành công mới đổi:

```dotenv
APP_DATABASE_BACKEND=supabase
```

### Ghi chú quan trọng

- `SUPABASE_SECRET_KEY` chỉ được dùng ở Backend, không đưa vào HTML, JavaScript hoặc repository công khai.
- Supabase đã chạy được sau khi tạo schema và migrate dữ liệu. File `.env` hiện đã bật `APP_DATABASE_BACKEND=supabase`.
- Sau khi tạo key hợp lệ, hãy rotate key đã gửi trong hội thoại này.
