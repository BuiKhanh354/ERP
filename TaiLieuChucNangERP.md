# Tài Liệu Chức Năng Hệ Thống ERP

## Tổng Quan

Đây là một hệ thống ERP (Enterprise Resource Planning) được xây dựng bằng Django Framework, tích hợp AI (Google Gemini) để hỗ trợ phân tích và đề xuất. Hệ thống gồm **7 module chính** với phân quyền theo vai trò (Manager/Employee).

**Đường dẫn gốc:** `d:\ERP\ERP\`

---

## Cấu Trúc Thư Mục

```
d:\ERP\ERP\
├── core/           # Module lõi (Authentication, User, Notifications)
├── projects/       # Quản lý dự án và công việc
├── resources/      # Quản lý nhân sự và phòng ban
├── budgeting/      # Quản lý ngân sách và chi phí
├── clients/        # Quản lý khách hàng (CRM)
├── performance/    # Đánh giá hiệu suất
├── ai/             # Tích hợp AI (Gemini)
├── templates/      # Giao diện HTML
└── static/         # File tĩnh (CSS, JS)
```

---

## 1. Module Core (Lõi)

**Thư mục:** `d:\ERP\ERP\core\`

### 1.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\core\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `BaseModel` | 6-27 | Model cơ sở với các trường chung (created_at, updated_at, created_by, updated_by) |
| `PasswordResetOTP` | 30-45 | OTP đặt lại mật khẩu cho user |
| `Notification` | 48-82 | Thông báo cho từng user (bell + modal) |
| `UserProfile` | 85-132 | Hồ sơ mở rộng cho user (avatar, role Manager/Employee, theme sáng/tối) |
| `EmailChangeOTP` | 135-152 | OTP xác nhận đổi email trong trang Hồ sơ |
| `AccountDeleteOTP` | 155-171 | OTP xác nhận xoá tài khoản |
| `AIChatHistory` | 174-192 | Lịch sử chat AI cho người dùng |

### 1.2. Views - Xử lý logic
**File:** `d:\ERP\ERP\core\views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| `DashboardView` | 41-60 | Dashboard chính, yêu cầu đăng nhập |
| `LoginView` | 63-84 | Trang đăng nhập ERP |
| `LogoutView` | 87-104 | Đăng xuất và chuyển về trang login |
| `ForgotPasswordView` | 107-165 | Nhập email để gửi OTP quên mật khẩu |
| `OTPVerifyView` | 168-222 | Xác thực OTP và đặt lại mật khẩu mới |
| `ChangePasswordRequiredView` | 225-258 | Đổi mật khẩu bắt buộc cho user mới tạo |
| `ProfileView` | 261-590 | Trang hồ sơ cá nhân (update profile, change password, request email change) |
| `NotificationsListView` | 593-619 | API trả về danh sách thông báo (JSON) |
| `NotificationMarkReadView` | 622-633 | Đánh dấu đã đọc thông báo |
| `NotificationMarkAllReadView` | 636-651 | Đánh dấu tất cả thông báo là đã đọc |

### 1.3. Admin Views
**File:** `d:\ERP\ERP\core\admin_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| Quản trị Admin | 1-836 | Quản lý users, tạo tài khoản với role, cấu hình hệ thống |

### 1.4. AI Chat Views
**File:** `d:\ERP\ERP\core\ai_chat_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| AI Chat | 1-280 | Chat với AI Assistant, lưu lịch sử chat |

### 1.5. AI Insights Views
**File:** `d:\ERP\ERP\core\ai_insights_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| AI Insights | 1-166 | Xem AI Insights trên dashboard |

### 1.6. Analytics Views
**File:** `d:\ERP\ERP\core\analytics_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| Analytics | 1-315 | Báo cáo phân tích, biểu đồ |

### 1.7. Forms
**File:** `d:\ERP\ERP\core\forms.py`

| Form | Dòng | Chức năng |
|------|------|-----------|
| LoginForm, ForgotPasswordForm, OTPVerifyForm, ProfileForm, PasswordChangeForm | 1-312 | Forms cho các chức năng xác thực và hồ sơ |

### 1.8. Services
**File:** `d:\ERP\ERP\core\services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| OTP Generation, Email Sending | 1-584 | Business logic: tạo OTP, gửi email |

### 1.9. Mixins
**File:** `d:\ERP\ERP\core\mixins.py`

| Mixin | Dòng | Chức năng |
|-------|------|-----------|
| `ManagerRequiredMixin` | 1-62 | Kiểm tra quyền Manager |

### 1.10. Notification Service
**File:** `d:\ERP\ERP\core\notification_service.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| NotificationService | 1-37 | Service gửi thông báo đến user |

---

## 2. Module Projects (Quản Lý Dự Án)

**Thư mục:** `d:\ERP\ERP\projects\`

### 2.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\projects\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `Project` | 9-54 | Dự án với trạng thái, priority, budget, departments, ngân sách nhân sự |
| `Task` | 57-102 | Công việc với assigned_to, status, estimated_hours, assignment_status |
| `TimeEntry` | 105-118 | Chấm công theo task, employee, date, hours |
| `PersonnelRecommendation` | 121-158 | Lịch sử đề xuất nhân sự từ AI |
| `PersonnelRecommendationDetail` | 161-191 | Chi tiết đề xuất nhân sự (through model) |

### 2.2. Web Views - Quản lý dự án
**File:** `d:\ERP\ERP\projects\web_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| `ProjectListView` | 25-107 | Danh sách dự án với filter và search |
| `ProjectDetailView` | 110-241 | Chi tiết dự án với tasks, budget, timeline |
| `ProjectCreateView` | 244-311 | Tạo dự án mới (chỉ Manager) |
| `ProjectUpdateView` | 314-406 | Cập nhật dự án |
| `ProjectDeleteView` | 409-432 | Xóa dự án |
| `PersonnelRecommendationView` | 435-529 | Đề xuất nhân sự AI cho dự án |
| `PersonnelRecommendationDetailView` | 532-543 | Xem chi tiết đề xuất nhân sự |
| `ApplyPersonnelRecommendationView` | 546-617 | Áp dụng đề xuất nhân sự vào dự án |
| `BudgetMonitoringView` | 620-639 | API kiểm tra ngân sách dự án |

### 2.3. Task Views - Quản lý công việc
**File:** `d:\ERP\ERP\projects\task_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| TaskListView, TaskCreateView, TaskUpdateView, TaskDeleteView | 1-737 | CRUD tasks, cập nhật trạng thái, giao/nhận việc |

### 2.4. Time Entry Views - Chấm công
**File:** `d:\ERP\ERP\projects\time_entry_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| TimeEntryListView, TimeEntryCreateView | 1-352 | Chấm công, xem lịch sử time entries |

### 2.5. Forms
**File:** `d:\ERP\ERP\projects\forms.py`

| Form | Dòng | Chức năng |
|------|------|-----------|
| ProjectForm, TaskForm, TimeEntryForm | 1-355 | Forms cho Project, Task, TimeEntry |

### 2.6. Services
**File:** `d:\ERP\ERP\projects\services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| ProjectService | 1-189 | Business logic cho project |

### 2.7. Personnel Services
**File:** `d:\ERP\ERP\projects\personnel_services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| PersonnelService | 1-557 | Tính toán phân bổ nhân sự, chi phí, workload |

---

## 3. Module Resources (Quản Lý Nhân Sự)

**Thư mục:** `d:\ERP\ERP\resources\`

### 3.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\resources\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `Department` | 6-16 | Phòng ban với tên, mô tả, manager |
| `Position` | 19-31 | Chức vụ với tên, mô tả, trạng thái hoạt động |
| `Employee` | 34-65 | Nhân viên với loại hợp đồng, lương/giờ, phòng ban, chức vụ |
| `ResourceAllocation` | 68-86 | Phân bổ nhân sự vào dự án với tỷ lệ % |
| `PayrollSchedule` | 89-131 | Lịch phát lương chung cho toàn bộ nhân viên |
| `EmployeeHourlyRate` | 134-151 | Lịch sử mức lương/giờ theo tháng |

### 3.2. Web Views - Quản lý nhân sự
**File:** `d:\ERP\ERP\resources\web_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| `EmployeeListView` | 22-83 | Danh sách nhân sự với filter |
| `EmployeeDetailView` | 86-127 | Chi tiết nhân sự với dự án tham gia |
| `EmployeeCreateView` | 130-192 | Tạo nhân sự mới (chỉ Manager) |
| `EmployeeUpdateView` | 195-244 | Cập nhật nhân sự |
| `EmployeeDeleteView` | 247-333 | Xóa nhân sự (chỉ Manager) |
| `DepartmentListView` | 336-360 | Danh sách phòng ban |
| `DepartmentCreateView` | 363-380 | Tạo phòng ban mới (chỉ Manager) |
| `DepartmentUpdateView` | 383-404 | Cập nhật phòng ban |

### 3.3. Salary Views
**File:** `d:\ERP\ERP\resources\salary_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| SalaryListView, SalaryDetailView | 1-207 | Xem và tính toán lương theo tháng |

### 3.4. Salary Services
**File:** `d:\ERP\ERP\resources\salary_services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| SalaryService | 1-175 | Tính lương dựa trên time entries và hourly rate |

### 3.5. Performance Services
**File:** `d:\ERP\ERP\resources\performance_services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| EmployeePerformanceService | 1-108 | Dịch vụ đánh giá hiệu suất nhân viên |

### 3.6. Forms
**File:** `d:\ERP\ERP\resources\forms.py`

| Form | Dòng | Chức năng |
|------|------|-----------|
| EmployeeForm, DepartmentForm, PositionForm, ResourceAllocationForm | 1-223 | Forms cho Employee, Department, Position, Allocation |

---

## 4. Module Budgeting (Quản Lý Ngân Sách)

**Thư mục:** `d:\ERP\ERP\budgeting\`

### 4.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\budgeting\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `BudgetCategory` | 6-17 | Danh mục ngân sách phân cấp (parent/children) |
| `Budget` | 20-44 | Ngân sách dự án theo năm tài chính (allocated/spent amount) |
| `Expense` | 47-71 | Chi phí với loại chi phí, vendor, invoice |

### 4.2. Web Views - Quản lý ngân sách
**File:** `d:\ERP\ERP\budgeting\web_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| `BudgetListView` | 20-194 | Danh sách ngân sách với filter, biểu đồ phân tích |
| `BudgetDetailView` | 197-269 | Chi tiết ngân sách với expenses |
| `BudgetCreateView` | 272-294 | Tạo ngân sách mới (chỉ Manager) |
| `BudgetUpdateView` | 297-323 | Cập nhật ngân sách (chỉ Manager) |
| `BudgetDeleteView` | 326-339 | Xóa ngân sách (chỉ Manager) |
| `ExpenseCreateView` | 342-438 | Tạo chi phí mới |
| `CreateBudgetCategoryView` | 441-474 | API tạo danh mục ngân sách (AJAX) |

### 4.3. Forms
**File:** `d:\ERP\ERP\budgeting\forms.py`

| Form | Dòng | Chức năng |
|------|------|-----------|
| BudgetForm, ExpenseForm, BudgetCategoryForm | 1-160 | Forms cho Budget, Expense, BudgetCategory |

---

## 5. Module Clients (Quản Lý Khách Hàng - CRM)

**Thư mục:** `d:\ERP\ERP\clients\`

### 5.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\clients\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `Client` | 5-33 | Khách hàng với loại (individual/company/government), status, industry |
| `Contact` | 36-56 | Liên hệ của khách hàng (first_name, last_name, email, is_primary) |
| `ClientInteraction` | 59-83 | Lịch sử tương tác (meeting, call, email, proposal, contract) |

### 5.2. Web Views - Quản lý khách hàng
**File:** `d:\ERP\ERP\clients\web_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| ClientListView, ClientDetailView, ClientCreateView, ClientUpdateView, ClientDeleteView | 1-312 | CRUD Client, Contact, Interaction |

### 5.3. Forms
**File:** `d:\ERP\ERP\clients\forms.py`

| Form | Dòng | Chức năng |
|------|------|-----------|
| ClientForm, ContactForm, InteractionForm | 1-144 | Forms cho Client, Contact, Interaction |

---

## 6. Module Performance (Đánh Giá Hiệu Suất)

**Thư mục:** `d:\ERP\ERP\performance\`

### 6.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\performance\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `PerformanceMetric` | 6-29 | Chỉ số hiệu suất (efficiency, quality, productivity, customer_satisfaction, cost_effectiveness) |
| `PerformanceScore` | 32-50 | Điểm hiệu suất tổng hợp theo kỳ |

### 6.2. Web Views - Báo cáo hiệu suất
**File:** `d:\ERP\ERP\performance\web_views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| PerformanceListView, PerformanceDetailView | 1-251 | Xem báo cáo hiệu suất, so sánh nhân viên |

### 6.3. Services
**File:** `d:\ERP\ERP\performance\services.py`

| Service | Dòng | Chức năng |
|---------|------|-----------|
| PerformanceService | 1-221 | Tính toán điểm hiệu suất |

---

## 7. Module AI (Tích Hợp Trí Tuệ Nhân Tạo)

**Thư mục:** `d:\ERP\ERP\ai\`

### 7.1. Models - Định nghĩa dữ liệu
**File:** `d:\ERP\ERP\ai\models.py`

| Model | Dòng | Mô tả |
|-------|------|-------|
| `AIInsight` | 5-28 | Lưu trữ AI insights đã tạo (type, title, summary, insights, recommendations) |

### 7.2. Services - AI Service (Google Gemini)
**File:** `d:\ERP\ERP\ai\services.py`

| Method | Dòng | Chức năng |
|--------|------|-----------|
| `AIService._check_user_has_data()` | 24-179 | Kiểm tra user có đủ data để phân tích AI |
| `AIService._get_gemini_client()` | 181-191 | Khởi tạo Gemini client |
| `AIService._generate_insight()` | 193-313 | Tạo AI insight sử dụng Gemini |
| `AIService.analyze_resource_performance()` | 315-360 | Phân tích hiệu suất nguồn lực |
| `AIService.recommend_project_staffing()` | 362-419 | Đề xuất nhân sự tối ưu cho dự án |
| `AIService.analyze_budget_patterns()` | 421-468 | Phân tích mẫu ngân sách và đề xuất tối ưu |
| `AIService.analyze_sales_performance()` | 470-566 | Phân tích dữ liệu bán hàng, đề xuất cải thiện |
| `AIService.analyze_purchasing_patterns()` | 568-652 | Phân tích mẫu mua hàng/chi phí |
| `AIService.recommend_expense_optimization()` | 654-814 | Phân tích chi phí, đề xuất tối ưu chi tiêu |
| `AIService.generate_dashboard_insight()` | 816-955 | Tự động tạo insight cho dashboard |
| `AIService.predict_weekly_budget()` | 957-1034 | Dự đoán budget cho từng tuần |
| `AIService.recommend_personnel_for_project()` | 1036-1151 | Đề xuất nhân sự cho dự án sử dụng AI |

### 7.3. Views - API endpoints
**File:** `d:\ERP\ERP\ai\views.py`

| View | Dòng | Chức năng |
|------|------|-----------|
| AIInsightCreateView, AIInsightListView | 1-207 | API endpoints cho AI insights |

---

## Sơ Đồ Liên Kết Modules

```
┌──────────────────────────────────────────────────────────────┐
│                          CORE                                 │
│         (Authentication, Users, Notifications)                │
└───────────────────────────┬──────────────────────────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
    ▼                       ▼                       ▼
┌─────────┐           ┌──────────┐           ┌─────────┐
│ CLIENTS │◄─────────►│ PROJECTS │◄─────────►│RESOURCES│
│  (CRM)  │           │ (Tasks)  │           │(HR/Dept)│
└────┬────┘           └────┬─────┘           └────┬────┘
     │                     │                      │
     │                     ▼                      │
     │              ┌───────────┐                 │
     └─────────────►│ BUDGETING │◄────────────────┘
                    │(Expenses) │
                    └─────┬─────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ PERFORMANCE │
                   │  (Metrics)  │
                   └──────┬──────┘
                          │
                          ▼
                    ┌──────────┐
                    │    AI    │
                    │(Insights)│
                    └──────────┘
```

---

## Phân Quyền Chi Tiết

### Admin (Superuser)
- Toàn quyền quản trị hệ thống
- Tạo/xóa tài khoản người dùng
- Gán vai trò Manager/Employee
- Quản lý cấu hình hệ thống

### Manager (Quản lý)
- Xem tất cả dữ liệu
- Tạo/Sửa/Xóa: Projects, Tasks, Employees, Budgets, Clients
- Đề xuất và áp dụng phân bổ nhân sự
- Xem báo cáo và AI insights

### Employee (Nhân viên)
- Xem dự án/task được phân bổ
- Cập nhật trạng thái task
- Chấm công (Time Entry)
- Xem thông tin cá nhân
- Tạo chi phí cho dự án được phân bổ

---

## Công Nghệ Sử Dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | Django (Python) |
| Database | PostgreSQL / SQLite |
| AI | Google Gemini API |
| Frontend | HTML/CSS/JavaScript, Bootstrap |
| Authentication | Django Auth + Custom OTP |
| Email | SMTP (gửi OTP, thông báo) |

---

## Hướng Dẫn Cài Đặt

1. Xem file `d:\ERP\ERP\requirements.txt` để cài đặt dependencies
2. Cấu hình `d:\ERP\ERP\.env` từ `d:\ERP\ERP\.env.example`
3. Xem file `d:\ERP\ERP\huongdantaotaikhoan.txt` để tạo tài khoản quản trị

---

*Tài liệu được tạo tự động bởi AI Assistant - Cập nhật: 24/01/2026*


👉 RAG (Retrieval Augmented Generation)

Cách này:

Không train lại model

Chỉ nhúng dữ liệu riêng của bạn vào

Model đọc dữ liệu rồi trả lời

Cần:

Vector database (FAISS, Chroma)

Embedding model miễn phí

LLM local hoặc API