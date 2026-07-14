# API trung gian: xuất SQL lên Google Drive

Web sẽ gọi action `export_sql_report_to_drive` trên máy trạm. Máy trạm chạy Oracle, tạo file Excel tại chỗ, upload vào thư mục Google Drive, rồi trả link file về web.

## Cài trên máy trạm

1. Copy `docs/api_trung_gian_drive_export.py` thành `C:\VNPTCTO\api-trung-gian\main.py`.
2. Cài thêm thư viện:

```powershell
cd C:\VNPTCTO\api-trung-gian
python -m pip install fastapi uvicorn oracledb python-dotenv openpyxl google-api-python-client google-auth
```

3. Tạo service account Google Cloud, tải file JSON và đặt tại:

```text
C:\VNPTCTO\api-trung-gian\drive-service-account.json
```

4. Tạo thư mục Drive để chứa báo cáo, bấm Share thư mục đó cho email `client_email` trong file service account JSON quyền Editor.

5. Cập nhật `.env` trên máy trạm:

```dotenv
DB_HOST=...
DB_PORT=1521
DB_SERVICE=...
DB_USER=...
DB_PASS=...

GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=C:\VNPTCTO\api-trung-gian\drive-service-account.json
GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_DRIVE
EXPORT_DIR=C:\VNPTCTO\exports
EXPORT_PAGE_SIZE=5000
EXPORT_MAX_ROWS=1000000
```

Nếu web đang dùng `INTERNAL_API_TOKEN`, thêm cùng giá trị đó vào `.env` máy trạm:

```dotenv
API_TOKEN=...
```

6. Trên web, cấu hình cùng thư mục Drive để web biết cần dùng luồng xuất trên máy trạm:

- Cách 1: đặt biến môi trường Render `GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_DRIVE`.
- Cách 2: vào `Quản trị kết nối` > dòng `Google Drive`/`drive_storage`, cập nhật cấu hình JSON:

```json
{"folder":"ID_THU_MUC_DRIVE"}
```

7. Chạy thử:

```powershell
cd C:\VNPTCTO\api-trung-gian
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="*"
Invoke-RestMethod https://api.vnptcto.com/test-oracle
```

Khi web xuất Excel, kết quả hoàn tất sẽ là link Google Drive thay vì file tải trực tiếp từ Render.
