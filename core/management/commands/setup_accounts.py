"""
Django management command để tạo tài khoản admin và nhân viên mặc định cho hệ thống ERP.

Chạy lệnh:
    python manage.py setup_accounts
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Tao tai khoan admin va nhan vien mac dinh cho he thong ERP'

    # ── Thông tin tài khoản mặc định ──────────────────────────────
    ADMIN_USERNAME = 'admin'
    ADMIN_EMAIL = 'admin@erp.local'
    ADMIN_PASSWORD = 'Admin@123'

    EMPLOYEE_USERNAME = 'nhanvien'
    EMPLOYEE_EMAIL = 'nhanvien@erp.local'
    EMPLOYEE_PASSWORD = 'Nhanvien@123'

    def _create_or_update_user(self, username, email, password, is_superuser, role, label):
        """Tạo hoặc cập nhật user + profile."""
        user = User.objects.filter(username=username).first()

        if user:
            # Reset password cho user đã tồn tại
            user.set_password(password)
            if is_superuser:
                user.is_staff = True
                user.is_superuser = True
            user.save()
            self.stdout.write(self.style.WARNING(
                f'[UPDATE] {label} "{username}" da ton tai (id={user.id}) - da reset password'
            ))
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=is_superuser,
                is_superuser=is_superuser,
            )
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Da tao {label}: {username} / {password}'
            ))

        # Đảm bảo có UserProfile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': role},
        )
        if not created and profile.role != role:
            profile.role = role
            profile.save()

        return user

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SETUP TAI KHOAN ERP'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 1. Tài khoản Admin (superuser)
        self._create_or_update_user(
            username=self.ADMIN_USERNAME,
            email=self.ADMIN_EMAIL,
            password=self.ADMIN_PASSWORD,
            is_superuser=True,
            role=UserProfile.ROLE_MANAGER,
            label='Admin',
        )

        # 2. Tài khoản Nhân viên
        self._create_or_update_user(
            username=self.EMPLOYEE_USERNAME,
            email=self.EMPLOYEE_EMAIL,
            password=self.EMPLOYEE_PASSWORD,
            is_superuser=False,
            role=UserProfile.ROLE_EMPLOYEE,
            label='Nhan vien',
        )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('TAI KHOAN DA SAN SANG:'))
        self.stdout.write(f'  Admin     -> username: {self.ADMIN_USERNAME}  |  password: {self.ADMIN_PASSWORD}  |  role: manager')
        self.stdout.write(f'  Nhan vien -> username: {self.EMPLOYEE_USERNAME}  |  password: {self.EMPLOYEE_PASSWORD}  |  role: employee')
        self.stdout.write(self.style.SUCCESS('=' * 60))
