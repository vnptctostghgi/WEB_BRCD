# Schema quản trị Web

Dự án đang dùng FastAPI + Jinja2 + JavaScript thuần ở frontend và Supabase REST/SQLite ở lớp dữ liệu. Backend là nơi giữ secret key, trình duyệt không được nhận secret key.

## Bảng người dùng và vai trò

- `users`: lưu tài khoản đăng nhập, họ tên, vai trò, trạng thái, mã nhân viên, email, phòng ban và cờ `must_change_password`.
- `system_roles`: danh mục vai trò do quản trị viên cấu hình, ví dụ `admin`, `region_manager`, `data_entry`, `viewer`.
- `role`: hiện dùng trực tiếp trên bảng `users` với 2 giá trị chính:
  - `admin`: quản trị hệ thống, mặc định xem và thao tác tất cả chức năng.
  - `viewer`: người dùng thường, chỉ thấy chức năng được phân quyền.
- Khi cần ràng buộc chặt hơn ở bước sau, có thể đổi `users.role` thành khóa ngoại tham chiếu `system_roles.code`.

## Bảng chức năng và phân quyền chức năng

- `features`: danh mục chức năng theo cây, mã dùng dạng không dấu liền chữ, ví dụ `quantriweb`, `quantringuoidung`, `quantriketnoi`, `truyvansql`.
- `user_permissions`: liên kết người dùng với nhiều chức năng.
- Sidebar sau đăng nhập đọc `user.permissions` để hiển thị đúng chức năng được cấp. Riêng admin luôn được xem tất cả.
- Module `Quản trị menu` cập nhật `features.parent_code` và `features.sort_order` để đổi nhóm hoặc sắp xếp thứ tự module.

## Bảng phân vùng dữ liệu

- `data_regions`: danh mục phân vùng dữ liệu, mặc định:
  - `ALL`: Tất cả
  - `13`: Cần Thơ
  - `66`: Hậu Giang
  - `47`: Sóc Trăng
- `user_data_permissions`: liên kết người dùng với các phân vùng được xem.
- Các API báo cáo sau này cần lấy danh sách phân vùng của người dùng hiện tại rồi thêm điều kiện lọc vào câu truy vấn dữ liệu.

Ví dụ nguyên tắc lọc dữ liệu sau này:

```sql
where ma_tinh in (:allowed_region_codes)
```

Nếu người dùng là admin hoặc được chọn `Tất cả`, backend mới cho xem toàn bộ dữ liệu.

## Bảng kết nối hệ thống

- `system_connections`: lưu cấu hình kết nối DB cơ quan, DB web, FTP, Drive, Telegram, VPN.
- Các giá trị nhạy cảm như mật khẩu, token, secret key phải để trong biến môi trường, không ghi thẳng vào `config` và không trả ra trình duyệt.
