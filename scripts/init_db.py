"""
Database initialization script.
Run this after migrations to create initial data.
"""
import os
import sys
from pathlib import Path
import django
from dotenv import load_dotenv

# Ensure project root on sys.path so "erp" is importable when running this script directly
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables (e.g., DB credentials, SECRET_KEY)
load_dotenv(BASE_DIR / '.env')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')
django.setup()

from django.contrib.auth.models import User
from resources.models import Department, Employee
from clients.models import Client
from budgeting.models import BudgetCategory


def init_database():
    """Initialize database with sample data."""
    print("Initializing database...")
    
    # Create admin user if not exists
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("Created admin user (username: admin, password: admin123)")
    
    # Create sample departments
    if not Department.objects.exists():
        dept1 = Department.objects.create(name='Engineering', description='Engineering Department')
        dept2 = Department.objects.create(name='Sales', description='Sales Department')
        dept3 = Department.objects.create(name='Operations', description='Operations Department')
        print("Created sample departments")
    
    # Create sample budget categories
    if not BudgetCategory.objects.exists():
        BudgetCategory.objects.create(name='Labor', description='Labor costs')
        BudgetCategory.objects.create(name='Materials', description='Material costs')
        BudgetCategory.objects.create(name='Equipment', description='Equipment costs')
        BudgetCategory.objects.create(name='Travel', description='Travel expenses')
        print("Created sample budget categories")
    
    print("Database initialization complete!")


if __name__ == '__main__':
    init_database()

