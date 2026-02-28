"""
Django management command để cập nhật role cho user.

Chạy lệnh:
    python manage.py update_user_role --email thanhhung111120021@gmail.com --role manager
    python manage.py update_user_role --email thanhhung11112002@gmail.com --role employee
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Cap nhat role cho user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email cua user can cap nhat',
        )
        parser.add_argument(
            '--role',
            type=str,
            required=True,
            choices=['manager', 'employee'],
            help='Role can cap nhat (manager hoac employee)',
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        role = options['role']
        
        # Tim user
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(f'[OK] Tim thay user: {user.username} ({user.email})'))
        except User.DoesNotExist:
            raise CommandError(f'[ERROR] Khong tim thay user voi email: {email}')

        # Lay hoac tao profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            self.stdout.write(self.style.WARNING(f'  [INFO] Da tao profile moi cho user'))
        
        # Cap nhat role
        old_role = profile.role
        profile.role = role
        profile.save()
        
        role_display = 'Quan ly' if role == 'manager' else 'Nhan vien'
        self.stdout.write(self.style.SUCCESS(f'[THANH CONG] Da cap nhat role tu "{old_role}" thanh "{role}" ({role_display}) cho user: {user.username}'))
