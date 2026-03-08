"""
Management command to seed RBAC data for the Accountant role.

Creates:
- Role: "Kế toán" (Accountant)
- 16 Permissions for accounting operations
- RolePermission links
"""
from django.core.management.base import BaseCommand
from core.models import Role, Permission, RolePermission


ACCOUNTING_PERMISSIONS = [
    # Invoice
    {'code': 'VIEW_INVOICE', 'name': 'Xem hoá đơn', 'module': 'accounting'},
    {'code': 'CREATE_INVOICE', 'name': 'Tạo hoá đơn', 'module': 'accounting'},
    {'code': 'EDIT_INVOICE', 'name': 'Sửa hoá đơn', 'module': 'accounting'},
    {'code': 'DELETE_INVOICE', 'name': 'Xoá hoá đơn', 'module': 'accounting'},
    # Expense
    {'code': 'VIEW_EXPENSE', 'name': 'Xem chi phí', 'module': 'accounting'},
    {'code': 'CREATE_EXPENSE', 'name': 'Tạo chi phí', 'module': 'accounting'},
    {'code': 'EDIT_EXPENSE', 'name': 'Sửa chi phí', 'module': 'accounting'},
    {'code': 'DELETE_EXPENSE', 'name': 'Xoá chi phí', 'module': 'accounting'},
    # Payment
    {'code': 'VIEW_PAYMENT', 'name': 'Xem thanh toán', 'module': 'accounting'},
    {'code': 'CREATE_PAYMENT', 'name': 'Tạo thanh toán', 'module': 'accounting'},
    {'code': 'EDIT_PAYMENT', 'name': 'Sửa thanh toán', 'module': 'accounting'},
    # Budget
    {'code': 'VIEW_BUDGET', 'name': 'Xem ngân sách', 'module': 'accounting'},
    {'code': 'CREATE_BUDGET', 'name': 'Tạo ngân sách', 'module': 'accounting'},
    {'code': 'EDIT_BUDGET', 'name': 'Sửa ngân sách', 'module': 'accounting'},
    # Report
    {'code': 'VIEW_REPORT', 'name': 'Xem báo cáo tài chính', 'module': 'accounting'},
    # Project (view only)
    {'code': 'VIEW_PROJECT', 'name': 'Xem dự án', 'module': 'projects'},
]


class Command(BaseCommand):
    help = 'Seed RBAC data for the Accountant (Kế toán) role'

    def handle(self, *args, **options):
        # Create / update permissions
        created_perms = 0
        for perm_data in ACCOUNTING_PERMISSIONS:
            perm, created = Permission.objects.get_or_create(
                code=perm_data['code'],
                defaults={
                    'name': perm_data['name'],
                    'module': perm_data['module'],
                    'description': perm_data['name'],
                },
            )
            if created:
                created_perms += 1
                self.stdout.write(self.style.SUCCESS(f'  Created permission: {perm.code}'))
            else:
                self.stdout.write(f'  Permission already exists: {perm.code}')

        # Create role
        role, role_created = Role.objects.get_or_create(
            name='ACCOUNTANT',
            defaults={
                'description': 'Accountant role - manages project finances',
                'is_active': True,
            },
        )
        if role_created:
            self.stdout.write(self.style.SUCCESS('Created role: ACCOUNTANT'))
        else:
            self.stdout.write('Role already exists: ACCOUNTANT')

        # Link permissions to role
        linked = 0
        for perm_data in ACCOUNTING_PERMISSIONS:
            perm = Permission.objects.get(code=perm_data['code'])
            rp, rp_created = RolePermission.objects.get_or_create(
                role=role,
                permission=perm,
            )
            if rp_created:
                linked += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {created_perms} permissions, linked {linked} new permissions to role "Ke toan (Accountant)".'
        ))
