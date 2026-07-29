# API trung gian: xuat SQL len Google Drive

Web se goi action `export_sql_report_to_drive` tren may tram. May tram chay Oracle, tao file Excel tai cho, upload vao thu muc Google Drive, roi tra link file ve web.

OneBSS dung cung duong Drive nay nhung khong can Oracle: worker OneBSS tai file bao cao xong se goi action `upload_file_to_drive` de API trung gian upload file do len Google Drive va tra link ve web.

## Mac dinh: dung OAuth cho thu muc share binh thuong

Tai khoan Google cua anh khong co Shared Drive thi dung OAuth. File se upload bang tai khoan Google da duoc share thu muc, giong cach upload binh thuong trong Google Drive.

Bo cai tu web se tu sinh cac cau hinh nay khi web da ket noi Google Drive OAuth:

```dotenv
GOOGLE_DRIVE_AUTH_MODE=oauth
GOOGLE_DRIVE_OAUTH_CLIENT_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-client.json
GOOGLE_DRIVE_OAUTH_TOKEN_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-token.json
GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_DUOC_SHARE
```

Neu web chua co OAuth token, vao trang quan tri web va bam ket noi Google Drive truoc khi tai lai bo cai may tram.

## Cai tren may tram

1. Copy `docs/api_trung_gian_drive_export.py` thanh `C:\VNPTCTO\api-trung-gian\main.py`.
2. Cai thu vien:

```powershell
cd C:\VNPTCTO\api-trung-gian
python -m pip install fastapi uvicorn oracledb python-dotenv openpyxl google-api-python-client google-auth google-auth-oauthlib
```

3. Cap nhat `.env`:

```dotenv
API_TOKEN=...
DB_DSN=10.92.53.53:1521/DBCTO
DB_HOST=...
DB_PORT=1521
DB_SERVICE=...
DB_SID=
DB_USER=...
DB_PASS=...

GOOGLE_DRIVE_AUTH_MODE=oauth
GOOGLE_DRIVE_OAUTH_CLIENT_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-client.json
GOOGLE_DRIVE_OAUTH_TOKEN_FILE=C:\VNPTCTO\api-trung-gian\drive-oauth-token.json
GOOGLE_DRIVE_FOLDER_ID=ID_THU_MUC_DUOC_SHARE
EXPORT_DIR=C:\VNPTCTO\exports
EXPORT_PAGE_SIZE=5000
EXPORT_MAX_ROWS=1000000
```

`DB_DSN` la uu tien so 1. Neu web da cau hinh host/port/service, bo cai se tu tao `DB_DSN` dang TCP, vi du `10.92.53.53:1521/DBCTO`. Khong dung `DB_DSN=/` vi day la ket noi local/bequeath va se loi tren python-oracledb thin mode.

4. Neu cai thu cong va chua co token OAuth, mo tren may tram:

```powershell
Start-Process "http://127.0.0.1:8000/drive-oauth/start"
```

Dang nhap tai khoan Google da duoc share thu muc, bam Allow, sau do kiem tra `/test-drive`.

## Luu y ve Service Account

Service Account khong upload duoc vao thu muc My Drive share thong thuong vi Google bao `Service Accounts do not have storage quota`. Voi he thong cua anh, khong dung huong nay.
