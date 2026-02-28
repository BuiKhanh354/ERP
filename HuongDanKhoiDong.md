# Hướng dẫn khởi động dự án ERP chi tiết

Tài liệu này hướng dẫn chi tiết các bước để tải, thiết lập và chạy dự án ERP (Django + SQL Server + AI) trên môi trường Windows.

## Yêu cầu cần có:

Trước khi bắt đầu, hãy đảm bảo bạn đã cài đặt:

1.  **Python** (Phiên bản 3.10 trở lên).
2.  **Microsoft SQL Server** (và SQL Server Management Studio nếu cần).
3.  **ODBC Driver 17 (hoặc 18) for SQL Server**: Cần thiết để Python có thể kết nối với SQL Server. Tải từ trang chủ Microsoft.
4.  **Git** (Tùy chọn, để clone dự án nếu chưa có source code).

---

## Các bước khởi động dự án

### Bước 1: Mở Terminal (Command Prompt hoặc PowerShell)

Bạn có thể dùng Terminal tích hợp sẵn trong VS Code/Cursor hoặc mở Command Prompt/PowerShell độc lập.

Di chuyển đến thư mục chứa dự án:

```cmd
cd D:\ERP\ERP
```

### Bước 2: Kích hoạt môi trường ảo (Virtual Environment)

Dự án đã có sẵn thư mục `venv` chứa môi trường ảo. Việc kích hoạt môi trường ảo giúp cách ly các thư viện của dự án này với các dự án Python khác trên máy bạn.

- **Nếu bạn dùng Command Prompt (cmd):**

  ```cmd
  venv\Scripts\activate
  ```

- **Nếu bạn dùng PowerShell:**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  _(Lưu ý: Nếu PowerShell báo lỗi "cannot be loaded because running scripts is disabled", hãy mở PowerShell với quyền Administrator và chạy lệnh: `Set-ExecutionPolicy Unrestricted -Scope CurrentUser`, sau đó thử lại lệnh kích hoạt)._

**Dấu hiệu thành công:** Bạn sẽ thấy chữ `(venv)` xuất hiện ở đầu dòng lệnh, ví dụ: `(venv) D:\ERP\ERP>`.

### Bước 3: Cài đặt các thư viện phụ thuộc

Khi môi trường ảo đã được kích hoạt `(venv)`, hãy cài đặt tất cả các thư viện cần thiết cho dự án:

```cmd
pip install -r requirements.txt
```

_Quá trình này có thể mất một vài phút._

### Bước 4: Cấu hình biến môi trường (.env)

Dự án cần một file `.env` để lưu trữ các thông tin cấu hình nhạy cảm (như tài khoản database, API key).

1.  Tìm file có tên `.env.example` trong thư mục `D:\ERP\ERP`.
2.  Copy file đó và đổi tên bản copy thành `.env`.
3.  Mở file `.env` bằng trình soạn thảo (VS Code/Cursor/Notepad) và chỉnh sửa các thông số sau cho phù hợp với SQL Server của bạn:

```env
# Database Configuration (SQL Server)
DB_NAME=ERP_DB              # Tên database bạn muốn tạo
DB_USER=sa                  # Tên đăng nhập SQL Server (thường là sa)
DB_PASSWORD=MatKhauCuaBan   # Mật khẩu SQL Server của bạn
DB_HOST=localhost           # Địa chỉ máy chủ (thường là localhost)
DB_PORT=1433                # Cổng kết nối (mặc định 1433)

# AI Configuration (Gemini) - Tùy chọn, nếu cần dùng tính năng AI
GEMINI_API_KEY=your-gemini-api-key-here
```

### Bước 5: Khởi động Server

Dự án đã cung cấp sẵn một script thần thánh tên là `runserver.py`. Script này sẽ tự động làm mọi việc khó nhằn nhất cho bạn (tạo database, chạy migrations, tạo user mẫu...).

Chỉ cần chạy lệnh sau:

```cmd
python runserver.py
```

**Quá trình script thực hiện tự động:**

1.  Đọc cấu hình từ file `.env`.
2.  Kết nối SQL Server và tự động tạo database `ERP_DB` (nếu chưa có).
3.  Tạo và cập nhật cấu trúc các bảng (Migrations).
4.  Tạo sẵn các tài khoản mẫu (để bạn dễ test chức năng).
5.  Khởi động Django Development Server.

Khi thấy thông báo **"Server đã sẵn sàng!"**, bạn đã thành công.

### Bước 6: Truy cập trang web

Mở trình duyệt web (Chrome, Edge, Firefox...) và truy cập vào một trong hai địa chỉ sau:

- [http://localhost:8000](http://localhost:8000)
- [http://127.0.0.1:8000](http://127.0.0.1:8000)

_(Để tắt server, hãy nhấp vào cửa sổ Terminal đang chạy và nhấn tổ hợp phím `Ctrl + C`)._
