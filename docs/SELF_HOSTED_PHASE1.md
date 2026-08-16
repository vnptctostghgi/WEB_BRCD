# Giai đoạn 1: chạy VNPTCTO trên PC server

Mục tiêu của giai đoạn này là chuyển FastAPI khỏi Render nhưng giữ nguyên Supabase, URL công khai và giao tiếp của các máy trạm.

## Kiến trúc

```text
vnptcto.com
  -> Cloudflare Tunnel
  -> cloudflared (Docker)
  -> nginx:80 (Docker network)
  -> backend:8000 (FastAPI, một Uvicorn worker)
  -> Supabase
```

Backend không publish cổng ra LAN/Internet. Nginx chỉ bind vào `127.0.0.1:8080` để kiểm tra tại PC server. Cloudflared truy cập Nginx qua Docker network.

Ứng dụng chỉ chạy một Uvicorn worker vì các scheduler đang chạy trong tiến trình. Tăng số worker sẽ làm nhiều scheduler cùng nhận việc.

## 1. Chuẩn bị PC server

1. Cài Git và Docker Desktop/Engine.
2. Bật Docker tự khởi động sau reboot và tắt chế độ sleep của máy.
3. Clone repository:

```powershell
git clone https://github.com/vnptctostghgi/WEB_BRCD.git C:\VNPTCTO\WEB_BRCD
Set-Location C:\VNPTCTO\WEB_BRCD
```

4. Tạo cấu hình production:

```powershell
Copy-Item .env.server.example .env
notepad .env
```

Sao chép các giá trị production từ Render. Phải giữ nguyên các khóa Supabase, `OTP_ENCRYPTION_KEY`, Mobile Gateway, Google, Zalo và Telegram. Chỉ giữ `SESSION_SECRET` nếu nó đủ mạnh; nếu phải xoay khóa này, các phiên đăng nhập cũ sẽ hết hiệu lực và người dùng cần đăng nhập lại. Không commit `.env`.

## 2. Chạy backend và Nginx trước

Chưa bật Tunnel trong lần chạy đầu:

```powershell
docker compose config
docker compose build backend
docker compose up -d backend nginx
docker compose ps
Invoke-RestMethod http://127.0.0.1:8080/api/ping
```

Kết quả health hợp lệ chứa:

```json
{"ok": true, "status": "alive"}
```

Kiểm tra log và trạng thái bootstrap Supabase:

```powershell
docker compose logs --tail 200 backend
docker compose logs --tail 100 nginx
```

Không tiếp tục nếu backend chưa `healthy` hoặc bootstrap Supabase báo `failed`.

## 3. Tạo Cloudflare Tunnel thử nghiệm

Trong Cloudflare Zero Trust:

1. Tạo named tunnel cho PC server.
2. Chọn Docker và lấy tunnel token.
3. Điền token vào `CLOUDFLARE_TUNNEL_TOKEN` trong `.env`.
4. Tạo hostname thử nghiệm, ví dụ `origin.vnptcto.com`.
5. Đặt service URL của hostname là `http://nginx:80`.

Khởi động profile Tunnel:

```powershell
docker compose --profile tunnel up -d
docker compose ps
docker compose logs --tail 100 cloudflared
```

Không đặt token trong `compose.yaml`, lệnh shell, ảnh chụp hoặc Git.

## 4. Kiểm thử trước khi chuyển tên miền

Trên hostname thử nghiệm, xác nhận:

- `/api/ping` trả `ok=true`.
- Login và logout hoạt động.
- Tài khoản/phân quyền/dashboard lấy đúng dữ liệu Supabase.
- Mobile Gateway, OTP email/SMS và public feed hoạt động.
- OneBSS, SQL và FTP queue nhận/trả việc đúng.
- Upload/download file lớn hoạt động.
- Google Drive OAuth/callback và Zalo webhook không bị thay đổi ngoài ý muốn.
- Scheduler chỉ có một tiến trình thực thi.

Cookie production có cờ Secure. Kiểm tra đăng nhập qua hostname HTTPS, không dùng URL HTTP localhost.

## 5. Chuyển `vnptcto.com`

Chỉ chuyển khi hostname thử nghiệm đã đạt kiểm thử:

1. Chọn cửa sổ bảo trì ngắn.
2. Tạm dừng việc tạo job mới và ghi lại các job đang chạy.
3. Trong Tunnel, thêm/chuyển public hostname `vnptcto.com` đến `http://nginx:80`.
4. Kiểm tra `https://vnptcto.com/api/ping`, login và máy trạm.
5. Bật lại scheduler/worker và theo dõi log ít nhất 60 phút.

Cloudflare phải để SSL/TLS ở chế độ phù hợp với Tunnel; không tạo chứng chỉ origin hoặc mở cổng router chỉ để phục vụ Tunnel.

## 6. Cập nhật về sau

Chạy từ repository sạch:

```powershell
.\deploy\update.ps1 -EnableTunnel
```

Script chỉ fast-forward từ `origin/main`, build trước khi thay container, chờ health và in log nếu thất bại. Script từ chối chạy nếu checkout trên server có thay đổi chưa lưu.

## Vận hành và khôi phục

Các lệnh thường dùng:

```powershell
docker compose ps
docker compose logs --tail 200 backend
docker compose logs --tail 200 cloudflared
docker compose restart backend
docker compose --profile tunnel down
```

Volume `vnptcto_app_data` giữ file tạm và trạng thái browser. Database chính vẫn ở Supabase trong giai đoạn 1. Sao lưu volume nếu dữ liệu trong thư mục này cần giữ lâu dài.

Nếu Tunnel lỗi nhưng backend khỏe, kiểm tra `cloudflared` và cấu hình public hostname. Nếu backend lỗi, không đổi DNS; sửa stack thử nghiệm trước.
