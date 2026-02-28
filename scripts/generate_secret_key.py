"""
Generate a Django SECRET_KEY for use in .env file.
"""
import os
import sys

# Add parent directory to path to import Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')

try:
    from django.core.management.utils import get_random_secret_key
    secret_key = get_random_secret_key()
    print("\n" + "="*60)
    print("Your Django SECRET_KEY:")
    print("="*60)
    print(secret_key)
    print("="*60)
    print("\nCopy this key and paste it into your .env file as:")
    print("SECRET_KEY=" + secret_key)
    print("\n")
except ImportError:
    # Fallback if Django is not installed yet
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    secret_key = ''.join(secrets.choice(alphabet) for i in range(50))
    print("\n" + "="*60)
    print("Your Django SECRET_KEY (generated without Django):")
    print("="*60)
    print(secret_key)
    print("="*60)
    print("\nCopy this key and paste it into your .env file as:")
    print("SECRET_KEY=" + secret_key)
    print("\n")

