"""
Script tạo user mẫu cho hệ thống ERP.
Chạy sau khi đã migrate:

    python scripts/create_sample_users.py
"""
import os
import sys
from pathlib import Path

import django
from dotenv import load_dotenv


def setup_django():
    """Khởi tạo Django settings để script có thể dùng ORM."""
    BASE_DIR = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(BASE_DIR))
    load_dotenv(BASE_DIR / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp.settings")
    django.setup()


def create_sample_users():
    """Tạo khoảng 10 user mẫu với email hợp lệ và role."""
    from django.contrib.auth.models import User
    from core.models import UserProfile

    users_data = [
        ("pm.nv", "pmnv.nv@example.com", "manager"),
    ]

    default_password = "12345678"

    print("Tao user mau...")
    for username, email, role in users_data:
        # Kiem tra user da ton tai chua (theo username hoac email)
        user = None
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        elif User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
        
        if user:
            # User da ton tai, chi cap nhat role neu can
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.role != role:
                profile.role = role
                profile.save()
                print(f"- Cap nhat role cho {username}: {role}")
            else:
                print(f"- Bo qua {username} (da ton tai)")
            continue
        
        # User chua ton tai, tao moi
        user = User.objects.create_user(
            username=username,
            email=email,
            password=default_password,
            is_staff=False,
            is_active=True,
        )
        
        # Tao profile voi role
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        
        role_display = "Quan ly" if role == "manager" else "Nhan vien"
        print(f"- Da tao user: {user.username} / {email} (mat khau: {default_password}, role: {role_display})")

    print("Hoan tat tao user mau.")


if __name__ == "__main__":
    setup_django()
    create_sample_users()


