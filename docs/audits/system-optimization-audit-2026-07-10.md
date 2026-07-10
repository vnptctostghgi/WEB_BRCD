# Audit tối ưu hệ thống VNPT CTO - 2026-07-10

## Phạm vi và nguyên tắc

- Mục tiêu: nâng cấp hệ thống theo hướng bảo mật hơn, ổn định hơn, nhanh hơn, dễ dùng hơn, nhưng không đổi nghiệp vụ hiện tại và không làm mất dữ liệu.
- Trạng thái repo khi audit: `main` sạch, sau đó tạo nhánh tài liệu `codex/audit-system-review`.
- Repo GitHub đã kiểm tra qua API công khai: `vnptctostghgi/WEB_BRCD`, visibility `public`.
- Audit này không sửa code nghiệp vụ. Đầu ra là báo cáo để duyệt trước khi triển khai các PR nhỏ.
- Kiểm thử baseline: `python -m pytest` pass `59/59`; `python -m compileall app` pass.

## 1. Sơ đồ kiến trúc hiện tại

```text
Browser
  |
  | HTML/Jinja + /static/app.js + /static/styles.css
  v
FastAPI app: app/main.py
  |-- SessionMiddleware cookie brcd_session
  |-- Static file cache middleware
  |-- Global exception handler -> Telegram
  |-- Lifespan startup -> initialize repository + start scheduler threads
  |
  v
Presentation: app/presentation/routes.py
  |-- auth, users, permissions, menu, dashboard, reports, credentials
  |-- Google Drive OAuth, OneBSS, Zalo, Telegram, data mining, work tasks
  |-- one catch-all route for feature URLs
  |
  v
Application services
  |-- auth_service.py
  |-- database_service.py -> InternalApiClient -> internal FastAPI/Oracle layer
  |-- vault_service.py
  |-- connection_service.py
  |-- google_drive_service.py
  |-- onebss_report_service.py / onebss_data_mining_service.py
  |-- zalo_bot.py / zalo_auto_message_service.py
  |-- telegram_notifier.py
  |-- task_scheduler.py
  |
  v
Data access
  |-- app_repository.py: SQLite local repository
  |-- supabase_repository.py: Supabase REST/PostgREST repository
  |-- repository_factory.py: chọn backend theo APP_DATABASE_BACKEND
  |
  v
External systems
  |-- Supabase
  |-- Internal API / Oracle
  |-- OneBSS API/browser automation
  |-- Google Drive OAuth/API
  |-- Telegram Bot
  |-- Zalo Bot
```

Bằng chứng chính:

- FastAPI startup, scheduler và session nằm trong [app/main.py](../../app/main.py):20, [app/main.py](../../app/main.py):50, [app/main.py](../../app/main.py):70.
- `routes.py` có 97 route và gom nhiều domain trong cùng file [app/presentation/routes.py](../../app/presentation/routes.py):1226.
- Menu seed nằm song song ở SQLite và Supabase: [app/data_access/app_repository.py](../../app/data_access/app_repository.py):15, [app/data_access/supabase_repository.py](../../app/data_access/supabase_repository.py):23.
- Giao diện app có 15 view chính trong [app/presentation/templates/index.html](../../app/presentation/templates/index.html):144.

## 2. Danh sách file và số dòng

Không tính file ảnh binary khi đếm dòng.

| Dòng | File |
|---:|---|
| 5089 | `app/presentation/static/app.js` |
| 2807 | `app/presentation/static/styles.css` |
| 2275 | `app/presentation/routes.py` |
| 1847 | `tests/test_app.py` |
| 1809 | `app/data_access/app_repository.py` |
| 1567 | `app/application/onebss_report_service.py` |
| 1136 | `app/data_access/supabase_repository.py` |
| 899 | `app/application/database_service.py` |
| 497 | `sql/supabase_upgrade_admin_modules.sql` |
| 486 | `sql/supabase_schema.sql` |
| 484 | `app/presentation/templates/index.html` |
| 475 | `app/application/onebss_data_mining_service.py` |
| 343 | `app/application/zalo_auto_message_service.py` |
| 335 | `app/application/task_scheduler.py` |
| 314 | `app/application/google_drive_service.py` |
| 284 | `README.md` |
| 252 | `app/application/zalo_bot.py` |
| 146 | `app/application/connection_service.py` |
| 104 | `app/application/telegram_notifier.py` |
| 98 | `app/data_access/internal_api_client.py` |
| 70 | `app/application/auth_service.py` |
| 70 | `app/presentation/templates/login.html` |
| 65 | `app/main.py` |
| 52 | `app/presentation/static/login.js` |
| 51 | `app/settings.py` |
| 46 | `scripts/migrate_sqlite_to_supabase.py` |
| 42 | `app/application/vault_service.py` |
| 38 | `scripts/refresh_dashboard_chart_cache.py` |
| 30 | `docs/database_schema_admin_modules.md` |
| 29 | `supabase_connections_patch.sql` |
| 28 | `sql/supabase_connections_patch.sql` |
| 13 | `requirements.txt` |
| 10 | `app/data_access/repository_factory.py` |

Tài sản binary: `app/presentation/static/login-hero.png`, `app/presentation/static/images/system-logo.png`.

## 3. Sơ đồ menu hiện tại

Nguồn menu hiện tại gồm 2 lớp: fallback tĩnh trong Jinja và cây `features` nạp lại bằng JS từ API.

```text
Tổng quan

Quản lý công việc

Quản trị web
  - Tài khoản web
    - Xem danh sách tài khoản
    - Thêm và sửa tài khoản
    - Xem mật khẩu đã lưu
  - Quản trị người dùng
  - Quản trị menu
  - Quản trị danh mục
    - Quản trị vai trò
  - Quản trị kết nối
    - Quản trị SQL
    - Quản trị dữ liệu OneBSS
  - Phân quyền
    - Người dùng
    - Dữ liệu
  - Nhật ký hoạt động

Truy vấn SQL

Báo cáo mới
  - Thiết kế Layout báo cáo
  - Đào dữ liệu OneBSS

Dashboard layout tự tạo
  - Có thể xuất hiện như mục con theo parent_code đã lưu
```

Bằng chứng:

- Seed menu SQLite: [app/data_access/app_repository.py](../../app/data_access/app_repository.py):15.
- Seed menu Supabase: [app/data_access/supabase_repository.py](../../app/data_access/supabase_repository.py):23.
- Fallback menu template: [app/presentation/templates/index.html](../../app/presentation/templates/index.html):57.
- JS dựng lại menu từ `/api/navigation`: [app/presentation/static/app.js](../../app/presentation/static/app.js):1693.

## 4. Sơ đồ menu đề xuất

Mục tiêu: người dùng thường chỉ thấy 5 đến 6 menu cấp một; kỹ thuật và cấu hình chỉ admin thấy.

```text
Tổng quan
  - KPI
  - Việc cần xử lý
  - Tác vụ đang chạy
  - Báo cáo gần đây
  - Cảnh báo liên quan

Điều hành và báo cáo
  - Tổng quan SXKD
  - Báo cáo của tôi
  - Kho báo cáo
  - Lịch sử chạy
  - Thiết kế báo cáo

Khai thác dữ liệu
  - Tạo yêu cầu
  - Tác vụ đang chạy
  - Kết quả
  - Lịch tự động
  - Nguồn dữ liệu

Truyền thông
  - Soạn và gửi
  - Lịch gửi
  - Mẫu nội dung
  - Nhật ký gửi

Công việc
  - Việc của tôi
  - Việc đã giao
  - Theo dõi tiến độ
  - Lịch nhắc

Quản trị hệ thống
  - Người dùng
  - Vai trò và quyền
  - Phạm vi dữ liệu
  - Danh mục
  - Kết nối
  - Nhật ký
  - Tác vụ nền
  - Cấu hình
```

Nguyên tắc migration: không xóa feature cũ ngay; tạo alias và chuyển `parent_code` theo nhóm mới, giữ route cũ hoạt động.

## 5. Sơ đồ luồng nghiệp vụ hiện tại

```text
Đăng nhập
  -> cookie session
  -> app shell
  -> JS tải /api/navigation
  -> chọn từng module riêng

SQL report
  -> admin cấu hình SQL trong Quản trị hệ thống
  -> người dùng chạy ở Truy vấn SQL
  -> dashboard builder chọn lại SQL để làm widget

Dashboard
  -> admin tạo page/tab/widget ở Dashboard Builder
  -> viewer mở dashboard
  -> tab load dữ liệu riêng
  -> có thể chụp ảnh
  -> admin chọn lịch Zalo để lưu ảnh

OneBSS
  -> admin cấu hình báo cáo OneBSS trong Quản trị hệ thống
  -> người dùng vào Đào dữ liệu OneBSS
  -> chạy request đồng bộ qua HTTP, có OTP/session
  -> tạo file
  -> upload Drive nếu có cấu hình
  -> ghi lịch sử

Zalo/Telegram
  -> cấu hình và test nằm trong Quản trị hệ thống
  -> lịch gửi Zalo nằm cùng khu vực hệ thống
  -> công việc nhắc Telegram nằm ở Quản lý công việc

Người dùng/quyền
  -> tạo người dùng
  -> sang phân quyền chức năng
  -> sang phân quyền dữ liệu
  -> sang dashboard hoặc thông báo nếu cần
```

## 6. Sơ đồ luồng nghiệp vụ mới

```text
Luồng khai thác dữ liệu thống nhất
  Chọn nguồn dữ liệu
  -> Chọn báo cáo
  -> Nhập tham số một lần
  -> Tạo job
  -> Worker xử lý
  -> Tạo file kết quả
  -> Lưu kho kết quả
  -> Upload Drive tùy chọn
  -> Cập nhật dashboard tùy chọn
  -> Gửi Zalo/Telegram tùy chọn
  -> Ghi lịch sử và audit

Luồng báo cáo đến dashboard
  Tạo báo cáo bằng wizard
  -> khai báo tham số
  -> chọn kiểu hiển thị
  -> cấp quyền/phạm vi dữ liệu
  -> chọn dashboard/vị trí
  -> chọn cache/lịch refresh
  -> preview
  -> công bố

Luồng dashboard đến công việc
  KPI/widget/bảng
  -> xem chi tiết
  -> tạo nhiệm vụ
  -> giao người phụ trách
  -> đặt hạn
  -> nhắc việc
  -> theo dõi
  -> đóng nhiệm vụ

Luồng quản trị người dùng
  Thông tin nhân viên
  -> Vai trò
  -> Quyền chức năng
  -> Phạm vi dữ liệu
  -> Dashboard mặc định
  -> Kênh nhận thông báo
  -> Xác nhận
```

## 7. 15 vấn đề quan trọng nhất

| # | Mức | Vấn đề | File/dòng | Ảnh hưởng | Cách khắc phục | Rủi ro khi sửa | Cách kiểm thử |
|---:|---|---|---|---|---|---|---|
| 1 | Critical | Repo public và có nhiều biến/token/secret reference trong code mẫu; cần quy trình private + rotate. | GitHub API; `.env.example`; [app/settings.py](../../app/settings.py):12 | Người ngoài thấy kiến trúc, endpoint, placeholder, tên biến tích hợp. | Chuyển repo private, bật secret scanning, rotate các secret từng dùng ở production. | Nếu rotate thiếu biến Render sẽ mất kết nối. | Kiểm tra GitHub visibility, Render env, smoke test login/dashboard/Zalo/Drive. |
| 2 | Critical | Production chưa fail-fast khi dùng secret/mật khẩu mặc định hoặc mock mode. | [app/settings.py](../../app/settings.py):12, [app/settings.py](../../app/settings.py):14, [app/main.py](../../app/main.py):21 | Production có thể chạy bằng `SESSION_SECRET` hoặc mật khẩu admin yếu/mặc định. | Thêm `validate_production_settings()` trước khi tạo app/lifespan. | Có thể làm Render không start nếu thiếu env. | Test startup production thiếu biến phải fail; production đủ biến phải start. |
| 3 | Critical | Chưa có CSRF cho các API mutation dùng cookie session. | Không có dấu vết `csrf`; session ở [app/main.py](../../app/main.py):50 | Người dùng đã đăng nhập có thể bị ép gọi POST/PUT/DELETE từ site khác. | CSRF token + Origin/Referer check cho mutation. | Có thể chặn frontend hiện tại nếu chưa thêm header token. | Test request không token bị chặn, request từ app hợp lệ pass. |
| 4 | High | Session là cookie session, chưa có server-side session, revoke, logout all devices, idle/absolute timeout, rotation sau login. | [app/main.py](../../app/main.py):50, [app/presentation/routes.py](../../app/presentation/routes.py):1264 | Không thể thu hồi phiên theo user/device; đổi/reset mật khẩu chưa revoke toàn bộ phiên. | Tạo bảng `sessions`, lưu session_id ký trong cookie, rotate sau login. | Migration có thể đăng xuất người dùng hiện tại. | Test login, logout, reset password revoke, khóa user revoke. |
| 5 | High | Vault và Google Drive token đang dẫn xuất khóa từ `SESSION_SECRET`, chưa có `VAULT_MASTER_KEY` và version. | [app/application/vault_service.py](../../app/application/vault_service.py):12, [app/application/google_drive_service.py](../../app/application/google_drive_service.py):67 | Đổi session secret có thể làm mất khả năng giải mã mật khẩu/token. | Thêm `VAULT_MASTER_KEY`, `VAULT_KEY_VERSION`, cơ chế decrypt bằng key cũ và re-encrypt. | Sai migration có thể làm credential không đọc được. | Backup, test decrypt cũ, rotate thử, rollback key cũ. |
| 6 | High | Exception handler gửi `str(exc)` thô sang Telegram; route test Telegram đang public, không yêu cầu đăng nhập. | [app/main.py](../../app/main.py):70, [app/presentation/routes.py](../../app/presentation/routes.py):2059 | Có thể lộ thông tin nội bộ và bị spam bot cảnh báo. | Sanitizer + request_id; khóa route test sau admin hoặc bỏ public. | Có thể thiếu thông tin debug nếu sanitize quá mạnh. | Test lỗi giả không chứa secret; route test cần admin. |
| 7 | High | Rate limit login mới đếm bền vững một phần, theo username và IP cuối cùng, chưa khóa tạm, chưa window rõ, chưa theo cặp username + IP. | [app/data_access/app_repository.py](../../app/data_access/app_repository.py):448, [app/data_access/app_repository.py](../../app/data_access/app_repository.py):686 | Chưa chống brute-force tốt trên nhiều IP/worker. | Mở rộng `login_attempts` với username, ip, window, locked_until, fail_count. | Cấu hình quá chặt có thể khóa nhầm user. | Test đúng/sai, khóa, tự mở, audit, không lộ user tồn tại. |
| 8 | High | Scheduler chạy trong web process bằng thread nền; scale nhiều instance có thể chạy trùng. | [app/main.py](../../app/main.py):20, [app/application/task_scheduler.py](../../app/application/task_scheduler.py):25 | Job gửi Telegram/Zalo/OneBSS/cache có thể chạy trùng hoặc mất khi restart. | Tách worker/scheduler, job lock bền vững, heartbeat. | Cần cấu hình thêm process trên Render. | Test lock, nhiều worker, restart giữa job. |
| 9 | High | Tác vụ nặng vẫn chạy trong HTTP request: OneBSS, Playwright screenshot, data mining run-now, Drive upload. | [app/presentation/routes.py](../../app/presentation/routes.py):1984, [app/presentation/routes.py](../../app/presentation/routes.py):2246, [app/presentation/routes.py](../../app/presentation/routes.py):2349 | Request lâu, timeout, giữ tài nguyên, UI phải chờ. | Tạo job queue chung trả `job_id`; UI theo dõi tiến độ. | Nếu thiếu trạng thái tiến độ, người dùng thấy mơ hồ. | Test tạo job, chạy worker, retry, cancel, xem log. |
| 10 | High | SQL report validator còn đơn giản; lỗi có thể trả preview SQL/tham số ra UI. | [app/presentation/routes.py](../../app/presentation/routes.py):998, [app/application/database_service.py](../../app/application/database_service.py):783 | Có rủi ro câu SQL phức tạp lọt kiểm tra hoặc lộ chi tiết Oracle/SQL. | SQL parser/allowlist SELECT, block comments/DDL/DML chắc hơn, sanitize lỗi. | Có thể chặn SQL hiện hữu nếu luật quá chặt. | Test SELECT pass, DDL/DML/comments/multi statement fail, lỗi không lộ chi tiết. |
| 11 | High | SSRF/URL/path guard chưa thống nhất. Google Sheet có host check nhưng follow redirect; Zalo photo cho mọi HTTPS; lưu local path Drive có thể chép tới đường dẫn admin nhập. | [app/presentation/routes.py](../../app/presentation/routes.py):1151, [app/presentation/routes.py](../../app/presentation/routes.py):1897, [app/presentation/routes.py](../../app/presentation/routes.py):591, [app/application/onebss_data_mining_service.py](../../app/application/onebss_data_mining_service.py):451 | Có thể gọi hoặc ghi tới nơi ngoài ý muốn nếu cấu hình bị lạm dụng. | Thêm module `safe_url`/`safe_path`, block private IP/metadata/file scheme/redirect xấu, giới hạn thư mục ghi. | Có thể chặn vài URL hợp lệ đang dùng. | Test localhost/private/metadata/file redirect bị chặn; docs/drive/onebss hợp lệ pass. |
| 12 | Medium | Upload import user chỉ kiểm tra đuôi `.xlsx` và đọc toàn bộ file; chưa kiểm tra size/content-type/zip bomb. | [app/presentation/routes.py](../../app/presentation/routes.py):1378 | File lớn hoặc giả mạo có thể tốn RAM hoặc gây lỗi parser. | Giới hạn kích thước, MIME, signature ZIP, số sheet/row, parse an toàn. | Có thể từ chối file Excel cũ nếu kiểm quá chặt. | Test file quá lớn, sai MIME, sai magic, workbook hợp lệ. |
| 13 | Medium | Pydantic model còn mutable default ở vài payload. | [app/presentation/routes.py](../../app/presentation/routes.py):246, [app/presentation/routes.py](../../app/presentation/routes.py):254, [app/presentation/routes.py](../../app/presentation/routes.py):272 | Dễ gây lỗi chia sẻ state ngầm hoặc cảnh báo khi nâng Pydantic. | Đổi sang `Field(default_factory=dict/list)`. | Rủi ro thấp. | Unit test payload mặc định độc lập. |
| 14 | High | Chưa có security headers/CSP/HSTS tập trung. | Chỉ có static cache ở [app/main.py](../../app/main.py):62 | Browser thiếu lớp bảo vệ chống clickjacking, MIME sniffing, referrer leak, CSP. | Middleware security headers, CSP theo nguồn CDN đang dùng. | CSP có thể chặn Tailwind CDN, Chart.js, html2canvas, Google Fonts nếu cấu hình thiếu. | Smoke test login/dashboard/assets; header assertions. |
| 15 | High | Chưa có GitHub Actions/CI và branch protection trong repo. | Không có `.github/`; `python -m pytest` pass local | Không có cổng tự động chặn lỗi trước merge/deploy. | Thêm CI: install, ruff/black check, pytest, secret scan, startup smoke. | CI ban đầu có thể fail do style hiện tại. | PR test bắt buộc pass trước merge. |

## 8. Chức năng trùng hoặc rời rạc

- Menu có 2 nguồn: Jinja fallback và JS dynamic navigation.
- Menu seed trùng giữa SQLite `FEATURE_ROWS` và Supabase `FEATURE_ROWS`.
- Quản trị kết nối, test kết nối, Drive OAuth, Telegram, Zalo, SQL, OneBSS đều nằm trong một view `system`.
- SQL report có 2 mặt: cấu hình trong `system`, chạy trong `reports`, dùng lại trong dashboard builder.
- OneBSS có cấu hình, chạy tay, lịch tự động, lưu file và Drive upload ở nhiều module.
- Zalo có webhook, log, test message, lịch tự động, capture dashboard rải ở routes/service/template/app.js.
- Telegram vừa là cảnh báo lỗi, vừa nhắc việc, vừa route test.
- Work task chưa liên kết ngữ cảnh dashboard/report/widget/filter.
- Audit log dùng chung, nhưng Zalo message log đang đọc lại từ audit log bằng parser.
- Data mining runs và OneBSS report runs là 2 lịch sử gần giống nhau.

## 9. Chức năng cần gộp

- Gộp OneBSS, Excel generation, Drive upload, dashboard refresh, Zalo/Telegram send vào `Job Center`.
- Gộp quản trị kết nối vào `Connection Center`, tách khỏi cấu hình SQL/OneBSS.
- Gộp SQL report config + widget/dashboard placement thành wizard báo cáo.
- Gộp tạo user + role + permission + data scope + default dashboard thành wizard user.
- Gộp Zalo/Telegram thành nhóm `Truyền thông` cho người dùng; phần token/webhook để trong admin.
- Gộp các danh sách lịch sử chạy vào một khái niệm `runs/jobs`.

## 10. Màn hình cần đơn giản hóa

1. `view-system`: quá nhiều việc kỹ thuật trong một màn hình.
2. `view-dashboard-builder`: nhiều card, nhiều thao tác cấu hình nâng cao lộ ra cùng lúc.
3. `view-onebss-mining`: cần thành flow tạo job, không giữ request chờ.
4. `view-reports`: nên là báo cáo của tôi/kho báo cáo, không chỉ truy vấn SQL.
5. `view-users`, `view-permissions`, `view-data-permissions`: nên thành wizard quản trị user.
6. `view-catalogs`: tách danh mục dùng thường xuyên và danh mục kỹ thuật.
7. `view-vault`: cần lọc/tìm/nhóm rõ, giảm thông tin nhạy cảm trên first view.
8. Zalo auto message dialog: nhiều trường, nên chia thành wizard hoặc progressive disclosure.
9. Login: nên đổi tên/brand theo phương án được duyệt, bổ sung show password/Caps Lock/loading/CAPTCHA sau nhiều lần sai.
10. Dashboard tổng quan: cần thêm việc cần làm, job đang chạy, cảnh báo có hành động.

## 11. Wireframe chữ cho màn hình chính

### Tổng quan

```text
[Bộ lọc vai trò/thời gian]
[KPI quan trọng] [Việc cần xử lý] [Tác vụ đang chạy]
[Cảnh báo ảnh hưởng] [Báo cáo gần đây] [Chức năng dùng gần đây]
```

### Job Center

```text
[Tabs: Đang chờ | Đang chạy | Thành công | Thất bại | Theo lịch]
[Bộ lọc loại job, người tạo, thời gian]
[Bảng job: trạng thái, tiến độ, bước hiện tại, kết quả, hành động xem log/chạy lại/hủy]
[Panel chi tiết: log đã sanitize, result reference, audit]
```

### Connection Center

```text
[Oracle] [Supabase] [Internal API] [OneBSS] [Google Drive] [Telegram] [Zalo]
Mỗi kết nối:
  trạng thái, lần kiểm tra cuối, độ trễ, chức năng phụ thuộc, tác vụ bị ảnh hưởng
  [Kiểm tra] [Cấu hình]
Không hiển thị secret.
```

### Report Wizard

```text
B1 Nguồn dữ liệu/SQL
B2 Tham số
B3 Hiển thị
B4 Quyền và phạm vi dữ liệu
B5 Dashboard/vị trí
B6 Cache/lịch refresh
B7 Preview và công bố
```

### Data Mining Flow

```text
[Nguồn dữ liệu] -> [Báo cáo] -> [Tham số] -> [Tùy chọn kết quả]
  Save file | Upload Drive | Update dashboard | Send Zalo/Telegram
[Tạo job]
[Theo dõi tiến độ]
```

### User Wizard

```text
B1 Nhân viên
B2 Vai trò
B3 Quyền chức năng
B4 Phạm vi dữ liệu
B5 Dashboard mặc định
B6 Kênh thông báo
B7 Xác nhận
```

## 12. 10 thay đổi nên làm trước

1. Chuyển repo private, bật secret scanning, lập checklist rotate secret production.
2. Thêm production startup validation, không cho chạy bằng secret/mật khẩu mặc định/mock.
3. Xóa hoặc bảo vệ `/api/test/telegram-alert`, thêm error sanitizer cho Telegram.
4. Thêm security headers cơ bản, bắt đầu CSP ở report-only nếu cần.
5. Thêm CSRF token và Origin check cho mutation API.
6. Hoàn thiện login rate limit: username + IP + window + lock.
7. Tách `SESSION_SECRET` khỏi `VAULT_MASTER_KEY`, thêm key version.
8. Tạo schema job tối thiểu và chuyển 1 flow nặng đầu tiên sang job: dashboard capture hoặc OneBSS run.
9. Tách `routes.py` theo router nhỏ mà không đổi URL.
10. Tạo GitHub Actions baseline: pytest + startup smoke + secret scan.

## 13. Branch plan

| Branch | Mục tiêu | Không làm |
|---|---|---|
| `codex/audit-system-review` | Lưu báo cáo này | Không sửa code |
| `codex/security-production-hardening` | Production validation, secret placeholders, docs off nếu cần | Không đổi auth/session lớn |
| `codex/security-alert-sanitizer` | Telegram sanitizer, khóa route test public | Không đổi workflow Zalo |
| `codex/security-csrf-headers` | CSRF, Origin check, security headers | Không đổi UI lớn |
| `codex/security-auth-session` | Rate limit, server-side session, revoke | Không đổi menu |
| `codex/security-vault-keys` | VAULT_MASTER_KEY, key version, rotate | Không đổi schema khác |
| `codex/architecture-job-center-foundation` | jobs/job_runs/job_logs/job_locks + UI tối thiểu | Chưa chuyển toàn bộ tác vụ |
| `codex/performance-onebss-job` | Chuyển OneBSS run sang job | Không đổi báo cáo SQL |
| `codex/architecture-split-routes` | Tách router theo domain, giữ URL cũ | Không đổi nghiệp vụ |
| `codex/ui-navigation-simplification` | Menu mới + alias URL | Không xóa feature |
| `codex/ui-design-system` | CSS variables/components, giảm card | Không đổi flow nghiệp vụ chưa duyệt |
| `codex/test-critical-flows` | Bổ sung test auth/session/job/CSRF/SQL/upload | Không refactor lớn |

## 14. Migration plan

Giai đoạn không cần migration DB:

- Production settings validation.
- Telegram sanitizer.
- Security headers.
- Tách router giữ URL cũ.
- Một phần cleanup mutable defaults.

Migration DB cần thiết:

- `sessions`: session_id hash, user_id, device, ip, user_agent, created_at, last_seen_at, expires_at, revoked_at.
- `login_attempts` mở rộng: username, ip, window_start, fail_count, locked_until, last_failed_at.
- `vault_keys` hoặc cột key metadata: key_version, encrypted_at, reencrypted_at.
- `jobs`, `job_runs`, `job_logs`, `job_locks`.
- Menu alias/redirect nếu cần: old_code, new_code, old_path, new_path, status.
- Audit log nâng cấp: request_id, ip, target_type, target_id, before_json, after_json, sanitized_result.

Yêu cầu trước migration:

- Backup Supabase và SQLite.
- Dry-run trên local SQLite và Supabase staging.
- Script verify row count trước/sau.
- Rollback script cho cột/bảng mới nếu chưa dùng.
- Không drop cột/bảng trong các PR đầu; chỉ add và dual-read/dual-write.

## 15. Rollback plan

- Mỗi PR độc lập, rollback bằng revert commit.
- Migrations giai đoạn đầu chỉ additive, rollback có thể tắt feature flag và giữ bảng mới.
- Production validation có flag tạm `ALLOW_INSECURE_STARTUP=false` chỉ dùng cho emergency và phải log cảnh báo.
- CSRF có thể triển khai report-only/monitor trước, sau đó enforce.
- Server-side session: cho chạy song song cookie cũ trong một thời gian ngắn, sau đó chuyển hẳn.
- Vault key rotation: luôn giữ key cũ đến khi verify toàn bộ credential decrypt được.
- Job worker: giữ endpoint đồng bộ cũ phía sau feature flag cho 1 bản deploy.
- Menu migration: giữ alias cũ và log truy cập URL cũ trước khi redirect.

## 16. Test plan

Test bắt buộc cho các PR đầu:

- Production startup thiếu `SESSION_SECRET`, `INITIAL_ADMIN_PASSWORD`, Supabase env, mock mode.
- Secret placeholder không cho production start.
- Đăng nhập đúng/sai, tài khoản bị khóa, tự mở khóa.
- CSRF token hợp lệ pass, thiếu/sai token fail.
- Origin/Referer lạ bị chặn.
- Session revoke khi logout, reset password, khóa user.
- Không trả password/token qua API connection/vault.
- Vault decrypt bằng key cũ và key mới.
- Upload `.xlsx` hợp lệ; file lớn/sai MIME/sai magic bị chặn.
- SQL report chỉ SELECT; DML/DDL/multi statement/comment bypass bị chặn.
- Lỗi Oracle/internal API không trả chi tiết nhạy cảm.
- SSRF validator chặn localhost, private IP, metadata, file scheme, redirect nội bộ.
- Job không chạy trùng khi nhiều worker.
- Scheduler lock.
- Google OAuth state.
- Telegram sanitizer.
- Menu theo quyền và alias URL cũ.
- OneBSS -> file -> Drive -> thông báo dưới dạng job.
- Báo cáo -> dashboard.
- Dashboard -> task.

CI nên chạy:

- `python -m pytest`
- `python -m compileall app`
- secret scan
- startup smoke development
- startup smoke production với env giả hợp lệ

## 17. Kế hoạch migration menu và URL

Hiện tại URL được giữ bằng catch-all route: [app/presentation/routes.py](../../app/presentation/routes.py):2660. Feature code alias đã có nền tảng ở [app/data_access/app_repository.py](../../app/data_access/app_repository.py):39.

Kế hoạch:

1. Xuất snapshot `features`, `user_permissions`, dashboard layout parent trước khi đổi.
2. Tạo bảng hoặc file mapping `old_code -> new_code`, `old_path -> new_path`.
3. Chỉ đổi `parent_code`, `sort_order`, `name` trong PR menu; không xóa code cũ.
4. JS navigation đọc menu mới nhưng route cũ vẫn mở view tương ứng.
5. Thêm server redirect 301/302 cho URL cũ chỉ sau khi xác nhận không mất bookmark.
6. Log URL cũ còn được dùng trong 2 tuần.
7. Sau khi ổn định mới cân nhắc ẩn alias khỏi menu, không xóa quyền ngay.

## 18. Kế hoạch giữ bookmark/URL cũ

- Giữ `/quantrimenu`, `/truyvansql`, `/baocaomoi`, `/thietkelayoutbaocao`, `/daodulieuonebss`, `/taikhoanweb`.
- Khi đổi menu, chỉ đổi vị trí hiển thị, không đổi `feature_code`.
- Nếu cần đổi slug, thêm redirect và alias trong `FEATURE_CODE_ALIASES`.
- Dashboard layout tự tạo giữ `page_id` và `feature_code` cũ; chỉ đổi `parent_code`.
- Với link Zalo scheduled screenshot đang lưu `page_url`, chạy script verify page_url trước migration.

## 19. Thay đổi có nguy cơ làm production ngừng hoạt động

- Production validation: thiếu env sẽ làm app không start.
- Repo private/rotate secret: Render deploy mất quyền clone hoặc env cũ hết hiệu lực.
- CSP/security headers: có thể chặn Tailwind CDN, Google Fonts, Chart.js, html2canvas.
- CSRF enforce: frontend chưa gửi token sẽ làm POST/PUT/DELETE fail.
- Server-side session: user có thể bị logout hàng loạt nếu migration không song song.
- Vault key separation: credential và OAuth token có thể không decrypt nếu thiếu key cũ.
- Job worker split: Render cần thêm worker/scheduler process; nếu không có worker, job sẽ đứng pending.
- SQL validator chặt hơn: một số report đang dùng `DEFINE` hoặc cú pháp Oracle đặc thù có thể bị chặn.
- Menu migration: quyền cũ có thể không khớp parent mới làm user mất menu.
- URL redirect: Zalo schedule, bookmark, dashboard page_url có thể trỏ sai nếu không alias.

## 20. Danh sách Pull Request nhỏ cần thực hiện

1. PR audit: thêm báo cáo này.
2. PR security config: production settings validation và tests.
3. PR alert sanitizer: Telegram sanitizer, request_id, bảo vệ test endpoint.
4. PR headers: security headers ở middleware.
5. PR CSRF: token + Origin check + frontend header.
6. PR rate limit: mở rộng login attempts và khóa tạm.
7. PR session: server-side session foundation.
8. PR vault key: VAULT_MASTER_KEY + key version + migration đọc key cũ.
9. PR upload hardening: size/MIME/magic/zip checks.
10. PR safe URL/path: SSRF/path guard dùng chung.
11. PR job schema: jobs/job_runs/job_logs/job_locks.
12. PR job UI: Job Center xem trạng thái/progress/log.
13. PR move dashboard capture to job.
14. PR move OneBSS run to job.
15. PR split routes auth/users/permissions.
16. PR split routes dashboard/reports.
17. PR split routes Zalo/Telegram/Drive/OneBSS.
18. PR menu data migration: nhóm menu mới, giữ URL cũ.
19. PR design system foundation.
20. PR report wizard foundation.
21. PR user wizard foundation.
22. PR CI baseline.

## 21. Bằng chứng kiểm thử và audit

- `python -m pytest`: `59 passed in 6.51s`.
- `python -m compileall app`: pass.
- `routes.py`: 97 route.
- `index.html`: 15 app views.
- `.github/`: chưa tồn tại.
- `.gitignore` đã chặn `.env`, `.venv`, `data`, `__pycache__`, `.pytest_cache`.
- Tracked placeholder/default secret literal xuất hiện ở `.env.example`, `README.md`, `app/settings.py`, `tests/test_app.py`; không in giá trị trong báo cáo này.

## Kết luận

Không nên viết lại hệ thống. Nên bắt đầu bằng nhóm PR bảo mật có rủi ro thấp và rollback rõ: production validation, sanitizer, CSRF/headers, rate limit, vault key. Sau đó mới chuyển tác vụ nặng sang job center, rồi tách code và làm gọn menu/giao diện. Cách này giữ nghiệp vụ hiện tại, giữ dữ liệu, và tạo nền để tối ưu hiệu năng thật thay vì chỉ chỉnh giao diện.
