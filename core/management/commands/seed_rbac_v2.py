"""
Seed RBAC v2: 4 roles + permission matrix for rebuilt scope.

Usage:
    python manage.py seed_rbac_v2
    python manage.py seed_rbac_v2 --deactivate-legacy
"""
from django.core.management.base import BaseCommand

from core.models import Permission, Role, RolePermission


ROLES = [
    ("ADMIN", "Quản trị hệ thống, user, role, audit."),
    ("MANAGER", "Vận hành dự án, nhân sự, duyệt công việc."),
    ("FINANCE", "Duyệt ngân sách/chi phí, báo cáo tài chính."),
    ("EMPLOYEE", "Thực thi task và chấm công cá nhân."),
]

PERMISSIONS = [
    # system
    ("system.user.create", "Tạo người dùng", "system"),
    ("system.user.update", "Cập nhật người dùng", "system"),
    ("system.user.deactivate", "Vô hiệu hóa người dùng", "system"),
    ("system.role.assign", "Gán role cho người dùng", "system"),
    ("system.audit.view", "Xem nhật ký hệ thống", "system"),
    # clients
    ("client.view.own", "Xem khách hàng của mình", "clients"),
    ("client.view.all", "Xem toàn bộ khách hàng", "clients"),
    ("client.create", "Tạo khách hàng", "clients"),
    ("client.update.own", "Sửa khách hàng của mình", "clients"),
    ("client.update.all", "Sửa toàn bộ khách hàng", "clients"),
    # projects/tasks/timesheet
    ("project.view.own", "Xem dự án được phân công", "projects"),
    ("project.view.all", "Xem toàn bộ dự án", "projects"),
    ("project.create", "Tạo dự án", "projects"),
    ("project.update", "Sửa dự án", "projects"),
    ("project.assign_member", "Phân công thành viên dự án", "projects"),
    ("task.view.own", "Xem task của mình", "projects"),
    ("task.view.team", "Xem task của team", "projects"),
    ("task.update.own", "Cập nhật task của mình", "projects"),
    ("task.submit_for_review", "Gửi task để review", "projects"),
    ("task.approve", "Duyệt task hoàn thành", "projects"),
    ("task.reject", "Từ chối task và yêu cầu sửa", "projects"),
    ("timesheet.create.own", "Tạo timesheet cá nhân", "projects"),
    ("timesheet.view.own", "Xem timesheet cá nhân", "projects"),
    ("timesheet.view.team", "Xem timesheet team", "projects"),
    ("timesheet.approve", "Duyệt timesheet", "projects"),
    # employees/salary
    ("employee.view.all", "Xem danh sách nhân sự", "resources"),
    ("employee.create", "Tạo hồ sơ nhân sự", "resources"),
    ("employee.update", "Cập nhật hồ sơ nhân sự", "resources"),
    ("salary.view", "Xem lương", "resources"),
    ("salary.update", "Cập nhật lương", "resources"),
    ("contract.update", "Cập nhật loại hợp đồng", "resources"),
    # finance
    ("budget.view", "Xem ngân sách", "finance"),
    ("budget.approve", "Duyệt ngân sách", "finance"),
    ("expense.view", "Xem chi phí", "finance"),
    ("expense.approve", "Duyệt chi phí", "finance"),
    ("finance.report.view", "Xem báo cáo tài chính", "finance"),
    ("finance.period.lock", "Khóa kỳ tài chính", "finance"),
    # ai
    ("ai.assistant.admin", "Sử dụng AI trợ lý Admin", "ai"),
    ("ai.assistant.manager", "Sử dụng AI trợ lý Manager", "ai"),
    ("ai.assistant.finance", "Sử dụng AI trợ lý Finance", "ai"),
    ("ai.assistant.employee", "Sử dụng AI trợ lý Employee", "ai"),
]

ROLE_PERMISSIONS = {
    "ADMIN": {
        "system.user.create",
        "system.user.update",
        "system.user.deactivate",
        "system.role.assign",
        "system.audit.view",
        "finance.report.view",
        "ai.assistant.admin",
    },
    "MANAGER": {
        "client.view.all",
        "client.create",
        "client.update.all",
        "project.view.all",
        "project.create",
        "project.update",
        "project.assign_member",
        "task.view.team",
        "task.update.own",
        "task.submit_for_review",
        "task.approve",
        "task.reject",
        "timesheet.view.team",
        "timesheet.approve",
        "employee.view.all",
        "employee.create",
        "employee.update",
        "salary.view",
        "salary.update",
        "contract.update",
        "ai.assistant.manager",
    },
    "FINANCE": {
        "budget.view",
        "budget.approve",
        "expense.view",
        "expense.approve",
        "finance.report.view",
        "finance.period.lock",
        "salary.view",
        "ai.assistant.finance",
    },
    "EMPLOYEE": {
        "client.view.own",
        "project.view.own",
        "task.view.own",
        "task.update.own",
        "task.submit_for_review",
        "timesheet.create.own",
        "timesheet.view.own",
        "ai.assistant.employee",
    },
}

LEGACY_ROLE_NAMES = {
    "HR_ADMIN",
    "PROJECT_MANAGER",
    "EXECUTIVE",
    "FINANCE_ADMIN",
    "ACCOUNTANT",
    "CFO",
    "RESOURCE_MANAGER",
}


class Command(BaseCommand):
    help = "Seed RBAC v2 with 4 roles and standardized permission matrix"

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-legacy",
            action="store_true",
            help="Deactivate legacy roles not used in v2 matrix.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Seeding RBAC v2 roles...")
        role_map = {}
        for name, desc in ROLES:
            role, _ = Role.objects.update_or_create(
                name=name,
                defaults={"description": desc, "is_active": True},
            )
            role_map[name] = role

        self.stdout.write("Seeding RBAC v2 permissions...")
        perm_map = {}
        for code, name, module in PERMISSIONS:
            perm, _ = Permission.objects.update_or_create(
                code=code,
                defaults={"name": name, "module": module},
            )
            perm_map[code] = perm

        self.stdout.write("Sync role-permission mapping...")
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role = role_map[role_name]
            wanted_ids = {perm_map[c].id for c in perm_codes}
            RolePermission.objects.filter(role=role).exclude(permission_id__in=wanted_ids).delete()
            for code in perm_codes:
                RolePermission.objects.get_or_create(role=role, permission=perm_map[code])

        if options.get("deactivate_legacy"):
            deactivated = Role.objects.filter(name__in=LEGACY_ROLE_NAMES).update(is_active=False)
            self.stdout.write(self.style.WARNING(f"Legacy roles deactivated: {deactivated}"))

        self.stdout.write(self.style.SUCCESS("RBAC v2 seed completed."))
