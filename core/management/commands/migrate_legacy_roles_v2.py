"""
Migrate legacy roles/profile role to RBAC v2 roles.

Usage:
    python manage.py migrate_legacy_roles_v2
    python manage.py migrate_legacy_roles_v2 --dry-run
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.models import Role, UserRole
from core.rbac import get_user_role_names


LEGACY_TO_V2 = {
    "ADMIN": "ADMIN",
    "HR_ADMIN": "MANAGER",
    "PROJECT_MANAGER": "MANAGER",
    "EXECUTIVE": "MANAGER",
    "RESOURCE_MANAGER": "MANAGER",
    "FINANCE_ADMIN": "FINANCE",
    "ACCOUNTANT": "FINANCE",
    "CFO": "FINANCE",
    "EMPLOYEE": "EMPLOYEE",
}


class Command(BaseCommand):
    help = "Map legacy role/profile role to RBAC v2 (ADMIN/MANAGER/FINANCE/EMPLOYEE)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        target_roles = {name: Role.objects.get(name=name) for name in ["ADMIN", "MANAGER", "FINANCE", "EMPLOYEE"]}
        changed = 0

        for user in User.objects.all().select_related("profile"):
            mapped = set()
            for old_name in get_user_role_names(user):
                v2_name = LEGACY_TO_V2.get(old_name)
                if v2_name:
                    mapped.add(v2_name)

            profile_role = getattr(getattr(user, "profile", None), "role", None)
            if profile_role == "manager":
                mapped.add("MANAGER")
            elif profile_role == "employee":
                mapped.add("EMPLOYEE")

            if not mapped:
                mapped.add("EMPLOYEE")

            for role_name in mapped:
                if dry_run:
                    self.stdout.write(f"[DRY] {user.username} -> {role_name}")
                else:
                    UserRole.objects.get_or_create(user=user, role=target_roles[role_name])
            changed += 1

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(f"{mode}: processed {changed} users."))
