"""
Management command: Seed ALL RBAC roles, permissions, and mappings.

Chạy: python manage.py seed_rbac
"""
from django.core.management.base import BaseCommand
from core.models import Role, Permission, RolePermission


# Tất cả roles theo lamviecvoiagent.md
ROLES = [
    ('ADMIN', 'Quản trị hệ thống — quản lý user, không xem lương/tài chính'),
    ('HR_ADMIN', 'Quản lý nhân sự — hồ sơ, lương, hợp đồng'),
    ('PROJECT_MANAGER', 'Quản lý dự án — tạo/sửa project, giao task, duyệt timesheet'),
    ('EMPLOYEE', 'Nhân viên — xem task, cập nhật task, ghi timesheet, xem hiệu suất'),
    ('EXECUTIVE', 'Lãnh đạo — xem tổng quan, read-only'),
    ('FINANCE_ADMIN', 'Tài chính — duyệt ngân sách, chi phí, khóa kỳ'),
    ('ACCOUNTANT', 'Kế toán — ghi nhận chi phí, xem báo cáo'),
    ('CFO', 'Giám đốc tài chính — toàn bộ tài chính'),
    ('RESOURCE_MANAGER', 'Quản lý nguồn lực — phân bổ, capacity'),
]

# Tất cả permissions theo lamviecvoiagent.md
PERMISSIONS = [
    # System Administration
    ('USER_CREATE', 'Tạo tài khoản người dùng', 'system'),
    ('USER_EDIT', 'Sửa thông tin người dùng', 'system'),
    ('USER_DEACTIVATE', 'Vô hiệu hóa tài khoản', 'system'),
    ('ROLE_ASSIGN', 'Gán role cho người dùng', 'system'),
    ('VIEW_USER_LIST', 'Xem danh sách người dùng', 'system'),
    ('VIEW_AUDIT_LOG', 'Xem nhật ký hệ thống', 'system'),
    ('manage_users', 'Quản lý người dùng (legacy)', 'system'),

    # HR
    ('VIEW_EMPLOYEE_PROFILE', 'Xem hồ sơ nhân sự', 'hr'),
    ('EDIT_EMPLOYEE_PROFILE', 'Sửa hồ sơ nhân sự', 'hr'),
    ('VIEW_SALARY_DETAIL', 'Xem chi tiết lương', 'hr'),
    ('EDIT_SALARY', 'Sửa lương', 'hr'),
    ('MANAGE_CONTRACT', 'Quản lý hợp đồng', 'hr'),

    # Project Management
    ('PROJECT_CREATE', 'Tạo dự án', 'projects'),
    ('PROJECT_EDIT', 'Sửa dự án', 'projects'),
    ('TASK_ASSIGN', 'Giao công việc', 'projects'),
    ('VIEW_PROJECT_COST_ESTIMATE', 'Xem chi phí ước tính', 'projects'),
    ('VIEW_PROJECT_ACTUAL_COST', 'Xem chi phí thực tế', 'projects'),
    ('APPROVE_TIMESHEET', 'Duyệt bảng chấm công', 'projects'),
    ('VIEW_ASSIGNED_TASK', 'Xem công việc được giao', 'projects'),
    ('UPDATE_TASK_STATUS', 'Cập nhật trạng thái công việc', 'projects'),
    ('SUBMIT_TIMESHEET', 'Nộp bảng chấm công', 'projects'),
    ('VIEW_ALL_PROJECTS', 'Xem tất cả dự án', 'projects'),
    ('VIEW_COMPANY_DASHBOARD', 'Xem dashboard công ty', 'projects'),
    ('VIEW_PROJECT_PROFIT', 'Xem lợi nhuận dự án', 'projects'),
    ('create_project', 'Tạo dự án (legacy)', 'projects'),
    ('edit_project', 'Sửa dự án (legacy)', 'projects'),
    ('delete_project', 'Xóa dự án (legacy)', 'projects'),
    ('log_time', 'Ghi nhận giờ làm', 'projects'),

    # Finance
    ('APPROVE_BUDGET', 'Phê duyệt ngân sách', 'finance'),
    ('EDIT_ACTUAL_COST', 'Sửa chi phí thực tế', 'finance'),
    ('VIEW_PROJECT_FINANCE', 'Xem tài chính dự án', 'finance'),
    ('LOCK_FINANCIAL_PERIOD', 'Khóa kỳ tài chính', 'finance'),
    ('EDIT_ACTUAL_FINANCE', 'Chỉnh sửa tài chính thực tế', 'finance'),
    ('approve_budget', 'Phê duyệt ngân sách (legacy)', 'finance'),
    ('approve_expense', 'Phê duyệt chi phí (legacy)', 'finance'),
    ('view_financial_report', 'Xem báo cáo tài chính', 'finance'),

    # Resource Management
    ('RESOURCE_ALLOCATE', 'Phân bổ nguồn lực', 'resources'),
    ('RESOURCE_EDIT', 'Sửa nguồn lực', 'resources'),
    ('VIEW_ALL_RESOURCES', 'Xem tất cả nguồn lực', 'resources'),

    # Performance
    ('view_performance', 'Xem hiệu suất', 'performance'),
]

# Role → Permission mappings theo lamviecvoiagent.md
ROLE_PERMISSIONS = {
    'ADMIN': [
        'USER_CREATE', 'USER_EDIT', 'USER_DEACTIVATE', 'ROLE_ASSIGN',
        'VIEW_USER_LIST', 'VIEW_AUDIT_LOG', 'manage_users',
    ],
    'HR_ADMIN': [
        'VIEW_EMPLOYEE_PROFILE', 'EDIT_EMPLOYEE_PROFILE',
        'VIEW_SALARY_DETAIL', 'EDIT_SALARY', 'MANAGE_CONTRACT',
    ],
    'PROJECT_MANAGER': [
        'PROJECT_CREATE', 'PROJECT_EDIT', 'TASK_ASSIGN',
        'VIEW_PROJECT_COST_ESTIMATE', 'VIEW_PROJECT_ACTUAL_COST',
        'APPROVE_TIMESHEET', 'create_project', 'edit_project',
        'delete_project', 'log_time', 'VIEW_ALL_PROJECTS',
    ],
    'EMPLOYEE': [
        'VIEW_ASSIGNED_TASK', 'UPDATE_TASK_STATUS', 'SUBMIT_TIMESHEET',
        'log_time', 'view_performance',
    ],
    'EXECUTIVE': [
        'VIEW_ALL_PROJECTS', 'VIEW_COMPANY_DASHBOARD', 'VIEW_PROJECT_PROFIT',
        'view_financial_report', 'view_performance',
    ],
    'FINANCE_ADMIN': [
        'APPROVE_BUDGET', 'EDIT_ACTUAL_COST', 'VIEW_PROJECT_FINANCE',
        'LOCK_FINANCIAL_PERIOD', 'approve_budget', 'approve_expense',
        'view_financial_report',
    ],
    'ACCOUNTANT': [
        'EDIT_ACTUAL_COST', 'VIEW_PROJECT_FINANCE', 'view_financial_report',
        'approve_expense',
    ],
    'CFO': [
        'APPROVE_BUDGET', 'EDIT_ACTUAL_COST', 'VIEW_PROJECT_FINANCE',
        'LOCK_FINANCIAL_PERIOD', 'EDIT_ACTUAL_FINANCE',
        'approve_budget', 'approve_expense', 'view_financial_report',
        'VIEW_PROJECT_PROFIT',
    ],
    'RESOURCE_MANAGER': [
        'RESOURCE_ALLOCATE', 'RESOURCE_EDIT', 'VIEW_ALL_RESOURCES',
    ],
}


class Command(BaseCommand):
    help = 'Seed all RBAC roles, permissions, and role-permission mappings'

    def handle(self, *args, **options):
        # 1. Roles
        self.stdout.write('Creating/updating Roles...')
        for name, desc in ROLES:
            role, created = Role.objects.update_or_create(
                name=name,
                defaults={'description': desc, 'is_active': True},
            )
            status = 'CREATED' if created else 'exists'
            self.stdout.write(f'  Role: {name} -- {status}')

        # 2. Permissions
        self.stdout.write('\nCreating/updating Permissions...')
        for code, name, module in PERMISSIONS:
            perm, created = Permission.objects.update_or_create(
                code=code,
                defaults={'name': name, 'module': module},
            )
            status = 'CREATED' if created else 'exists'
            self.stdout.write(f'  Permission: {code} -- {status}')

        # 3. Role-Permission mappings
        self.stdout.write('\nAssigning permissions to roles...')
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                self.stderr.write(f'  WARNING: Role {role_name} not found, skipping.')
                continue

            for pcode in perm_codes:
                try:
                    perm = Permission.objects.get(code=pcode)
                    _, created = RolePermission.objects.get_or_create(
                        role=role, permission=perm,
                    )
                    if created:
                        self.stdout.write(f'  {role_name} <- {pcode} (NEW)')
                except Permission.DoesNotExist:
                    self.stderr.write(f'  WARNING: Permission {pcode} not found, skipping.')

        self.stdout.write(self.style.SUCCESS('\nSeed RBAC completed!'))

