# API trung gian: xuất SQL lên Google Drive

Web sẽ gọi action `export_sql_report_to_drive` trên máy trạm. Máy trạm chạy Oracle, tạo file Excel tại chỗ, upload vào thư mục Google Drive, rồi trả link file về web.

## Cài trên máy trạm

1. Copy `docs/api_trung_gian_drive_export.py` thành `C:\VNPTCTO\api-trung-gian\main.py`.
2. Cài thêm thư viện:

```powershell
cd C:\VNPTCTO\api-trung-gian
python -m pip install fastapi uvicorn oracledb python-dotenv openpyxl google-api-python-client google-auth google-auth-oauthlib
```

3. Tạo service account Google Cloud, tải file JSON và đặt tại:

```text
C:\VNPTCTO\api-trung-gian\drive-service-account.json
```

4. Tạo **Google Shared Drive** để chứa báo cáo, không dùng thư mục thường trong My Drive. Thêm email `client_email` trong file service account JSON vào Shared Drive với quyền Content manager/Manager, rồi tạo một thư mục bên trong Shared Drive đó.

> Service Account không có quota lưu trữ riêng. Nếu upload vào My Drive hoặc một folder thường được share cho Service Account, Google Drive sẽ trả lỗi `Service Accounts do not have storage quota`.

5. Cập nhật `.env` trên máy trạm:

```dotenv
DB_HOST=...
DB_PORT=1521
DB_SERVICE=...
DB_USER=...
DB_PASS=...

GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=C:\VNPTCTO\api-trung-gian\drive-service-account.json
GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_TRONG_SHARED_DRIVE
EXPORT_DIR=C:\VNPTCTO\exports
EXPORT_PAGE_SIZE=5000
EXPORT_MAX_ROWS=1000000
```

Nếu web đang dùng `INTERNAL_API_TOKEN`, thêm cùng giá trị đó vào `.env` máy trạm:

```dotenv
API_TOKEN=...
```

6. Trên web, cấu hình cùng thư mục Drive để web biết cần dùng luồng xuất trên máy trạm:

- Cách 1: đặt biến môi trường Render `GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_TRONG_SHARED_DRIVE`.
- Cách 2: vào `Quản trị kết nối` > dòng `Google Drive`/`drive_storage`, cập nhật cấu hình JSON:

```json
{"folder":"ID_THU_MUC_TRONG_SHARED_DRIVE"}
```

7. Chạy thử:

```powershell
cd C:\VNPTCTO\api-trung-gian
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="*"
Invoke-RestMethod https://api.vnptcto.com/test-oracle
Invoke-RestMethod https://api.vnptcto.com/test-drive
```

Khi web xuất Excel, kết quả hoàn tất sẽ là link Google Drive thay vì file tải trực tiếp từ Render.

## Nếu không có quyền Shared Drive

Dùng OAuth bằng tài khoản Google thật của người dùng. File sẽ upload vào My Drive/folder thường và tính vào quota của tài khoản đó, không dùng quota Service Account.

1. Vào Google Cloud Console > APIs & Services > Credentials.
2. Tạo `OAuth client ID` loại `Desktop app`, tải file JSON và lưu tại:

```text
C:\VNPTCTO\api-trung-gian\drive-oauth-client.json
```

3. Cập nhật `.env` máy trạm:

```dotenv
GOOGLE_DRIVE_AUTH_MODE=oauth
GOOGLE_DRIVE_OAUTH_CLIENT_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-client.json
GOOGLE_DRIVE_OAUTH_TOKEN_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-token.json
GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_MY_DRIVE_HOAC_FOLDER_DUOC_SHARE
```

4. Restart API máy trạm, rồi mở trình duyệt trên máy trạm:

```powershell
Start-Process "http://127.0.0.1:8000/drive-oauth/start"
```

Đăng nhập tài khoản Google muốn dùng để chứa file, bấm Allow. Sau đó kiểm tra:

```powershell
Invoke-RestMethod https://api.vnptcto.com/test-drive
```

Kết quả đúng với OAuth sẽ có:

```text
status: ok
auth_mode: oauth
drive_type: my_drive
```

## Auto run on workstation

Run PowerShell as Administrator on the workstation:

```powershell
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/vnptctostghgi/WEB_BRCD/main/docs/install_api_trung_gian_task.ps1" `
  -OutFile "C:\VNPTCTO\install_api_trung_gian_task.ps1"

powershell -ExecutionPolicy Bypass -File "C:\VNPTCTO\install_api_trung_gian_task.ps1"
```

The script creates:

- `VNPTCTO API Trung Gian`: starts the local FastAPI middleware at boot.
- `VNPTCTO API Watchdog`: checks every 5 minutes and restarts the API/cloudflared if needed.

After it finishes, these checks must return `status: ok`:

```powershell
Invoke-RestMethod https://api.vnptcto.com/test-oracle
Invoke-RestMethod https://api.vnptcto.com/test-drive
```
