"""
Purge legacy roles and legacy role assignments after migration to 4-role model.

Usage:
    python manage.py purge_legacy_roles --dry-run
    python manage.py purge_legacy_roles --force
"""
from django.core.management.base import BaseCommand

from core.models import Role, RolePermission, UserRole


KEEP_ROLES = {"ADMIN", "MANAGER", "FINANCE", "EMPLOYEE"}


class Command(BaseCommand):
    help = "Delete legacy roles (and related mappings), keep only 4 roles."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview what will be deleted.")
        parser.add_argument("--force", action="store_true", help="Actually delete legacy role data.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        force = options.get("force", False)

        if not dry_run and not force:
            self.stdout.write(self.style.WARNING("Use --dry-run to preview or --force to apply deletion."))
            return

        legacy_roles = list(Role.objects.exclude(name__in=KEEP_ROLES))
        legacy_role_ids = [r.id for r in legacy_roles]

        ur_count = UserRole.objects.filter(role_id__in=legacy_role_ids).count()
        rp_count = RolePermission.objects.filter(role_id__in=legacy_role_ids).count()

        self.stdout.write(f"Legacy roles found: {len(legacy_roles)}")
        for role in legacy_roles:
            self.stdout.write(f" - {role.name}")
        self.stdout.write(f"UserRole rows to delete: {ur_count}")
        self.stdout.write(f"RolePermission rows to delete: {rp_count}")

        if dry_run and not force:
            self.stdout.write(self.style.SUCCESS("DRY-RUN completed. No data changed."))
            return

        UserRole.objects.filter(role_id__in=legacy_role_ids).delete()
        RolePermission.objects.filter(role_id__in=legacy_role_ids).delete()
        deleted_count, _ = Role.objects.filter(id__in=legacy_role_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Purge completed. Deleted objects: {deleted_count}"))
