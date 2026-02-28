"""
Management command để xóa toàn bộ data mẫu trong database.
Chạy: python manage.py clear_sample_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from projects.models import Project, Task, TimeEntry, PersonnelRecommendation, PersonnelRecommendationDetail
from resources.models import Employee, Department, Position, ResourceAllocation, PayrollSchedule, EmployeeHourlyRate
from budgeting.models import Budget, Expense
from clients.models import Client
from performance.models import PerformanceScore, PerformanceMetric
from core.models import Notification, AIChatHistory
from ai.models import AIInsight


class Command(BaseCommand):
    help = 'Xóa toàn bộ data mẫu trong database (giữ lại users và cấu hình hệ thống)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Xác nhận xóa data (bắt buộc)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '[WARNING] CANH BAO: Lenh nay se xoa TOAN BO data mau!\n'
                    'De xac nhan, chay: python manage.py clear_sample_data --confirm'
                )
            )
            return

        self.stdout.write(self.style.WARNING('Dang xoa toan bo data mau...'))

        # Xóa theo thứ tự để tránh lỗi foreign key
        deleted_counts = {}

        # 1. Xóa các bảng có foreign key phức tạp trước
        deleted_counts['PersonnelRecommendationDetail'] = PersonnelRecommendationDetail.objects.all().delete()[0]
        deleted_counts['PersonnelRecommendation'] = PersonnelRecommendation.objects.all().delete()[0]
        deleted_counts['TimeEntry'] = TimeEntry.objects.all().delete()[0]
        deleted_counts['Task'] = Task.objects.all().delete()[0]
        deleted_counts['Expense'] = Expense.objects.all().delete()[0]
        deleted_counts['Budget'] = Budget.objects.all().delete()[0]
        deleted_counts['ResourceAllocation'] = ResourceAllocation.objects.all().delete()[0]
        deleted_counts['PerformanceScore'] = PerformanceScore.objects.all().delete()[0]
        deleted_counts['PerformanceMetric'] = PerformanceMetric.objects.all().delete()[0]
        deleted_counts['EmployeeHourlyRate'] = EmployeeHourlyRate.objects.all().delete()[0]
        deleted_counts['Employee'] = Employee.objects.all().delete()[0]
        deleted_counts['Project'] = Project.objects.all().delete()[0]
        deleted_counts['Client'] = Client.objects.all().delete()[0]
        deleted_counts['Department'] = Department.objects.all().delete()[0]
        deleted_counts['Position'] = Position.objects.all().delete()[0]
        deleted_counts['Notification'] = Notification.objects.all().delete()[0]
        deleted_counts['AIChatHistory'] = AIChatHistory.objects.all().delete()[0]
        deleted_counts['AIInsight'] = AIInsight.objects.all().delete()[0]

        # PayrollSchedule - giữ lại vì là cấu hình hệ thống
        # Không xóa User vì cần giữ lại users

        # Tổng kết
        total_deleted = sum(deleted_counts.values())
        
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Da xoa thanh cong {total_deleted} ban ghi:'))
        for model_name, count in deleted_counts.items():
            if count > 0:
                self.stdout.write(f'   - {model_name}: {count} ban ghi')

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Hoan tat! Database da duoc lam sach.'))
        self.stdout.write(self.style.WARNING('[NOTE] Luu y: Users va PayrollSchedule van duoc giu lai.'))
