"""
Django management command để tạo user nhân viên.

Chạy lệnh:
    python manage.py create_employee_user --email employee@example.com --username employee --password Password123
    python manage.py create_employee_user --email employee@example.com  # Tự động tạo username và password
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import UserProfile
import secrets
import string


class Command(BaseCommand):
    help = 'Tao user nhan vien voi UserProfile role=employee'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email cua user nhan vien',
        )
        parser.add_argument(
            '--username',
            type=str,
            required=False,
            help='Username (tu dong tao neu khong chi dinh)',
        )
        parser.add_argument(
            '--password',
            type=str,
            required=False,
            help='Password (tu dong tao neu khong chi dinh)',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            required=False,
            default='',
            help='Ten cua user',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            required=False,
            default='',
            help='Ho cua user',
        )

    def generate_password(self, length=12):
        """Tạo password ngẫu nhiên."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        username = options.get('username') or email.split('@')[0]
        password = options.get('password')
        first_name = options.get('first_name', '')
        last_name = options.get('last_name', '')
        
        # Kiểm tra user đã tồn tại chưa
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            self.stdout.write(self.style.WARNING(f'[INFO] User voi email "{email}" da ton tai: {user.username}'))
            
            # Cập nhật role nếu chưa có hoặc chưa đúng
            profile, created = UserProfile.objects.get_or_create(user=user)
            if profile.role != UserProfile.ROLE_EMPLOYEE:
                old_role = profile.role
                profile.role = UserProfile.ROLE_EMPLOYEE
                profile.save()
                self.stdout.write(self.style.SUCCESS(f'[OK] Da cap nhat role tu "{old_role}" thanh "employee"'))
            else:
                self.stdout.write(self.style.SUCCESS(f'[OK] User da co role "employee"'))
            
            self.stdout.write(self.style.SUCCESS(f'[THANH CONG] User nhan vien: {user.username} ({user.email})'))
            return
        
        # Kiểm tra username đã tồn tại chưa
        if User.objects.filter(username=username).exists():
            # Tạo username mới bằng cách thêm số
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            self.stdout.write(self.style.WARNING(f'[INFO] Username da ton tai, su dung: {username}'))
        
        # Tạo password nếu chưa có
        if not password:
            password = self.generate_password()
            self.stdout.write(self.style.WARNING(f'[INFO] Password tu dong: {password}'))
        
        # Tạo user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False
            )
            self.stdout.write(self.style.SUCCESS(f'[OK] Da tao user: {user.username} ({user.email})'))
        except Exception as e:
            raise CommandError(f'[ERROR] Khong the tao user: {str(e)}')
        
        # Tạo profile với role employee
        try:
            profile = UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_EMPLOYEE
            )
            self.stdout.write(self.style.SUCCESS(f'[OK] Da tao UserProfile voi role=employee'))
        except Exception as e:
            # Nếu profile đã tồn tại, cập nhật role
            profile = UserProfile.objects.get(user=user)
            profile.role = UserProfile.ROLE_EMPLOYEE
            profile.save()
            self.stdout.write(self.style.SUCCESS(f'[OK] Da cap nhat UserProfile voi role=employee'))
        
        # Hiển thị thông tin
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('[THANH CONG] Da tao user nhan vien:'))
        self.stdout.write(f'  Username: {user.username}')
        self.stdout.write(f'  Email: {user.email}')
        if not options.get('password'):
            self.stdout.write(self.style.WARNING(f'  Password: {password}'))
        self.stdout.write(f'  Role: Nhan vien (employee)')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.WARNING('[LUU Y] Luu lai password de dang nhap!'))
