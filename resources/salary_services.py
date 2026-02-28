"""
Services for calculating employee hourly rates and managing salary history.
"""
from decimal import Decimal
from datetime import datetime, date
from calendar import monthrange
from django.utils import timezone
from django.db.models import Q
from .models import Employee, EmployeeHourlyRate


class HourlyRateService:
    """Service for calculating and managing hourly rates."""

    @staticmethod
    def calculate_working_hours_per_month(year, month, hours_per_day=8):
        """
        Tính tổng số giờ làm việc trong tháng.
        Quy tắc: 8 giờ/ngày, trừ thứ 7 và chủ nhật.
        
        Args:
            year: Năm
            month: Tháng (1-12)
            hours_per_day: Số giờ làm việc mỗi ngày (mặc định 8)
        
        Returns:
            Decimal: Tổng số giờ làm việc trong tháng
        """
        # Lấy số ngày trong tháng
        days_in_month = monthrange(year, month)[1]
        
        # Đếm số ngày làm việc (trừ thứ 7 và chủ nhật)
        working_days = 0
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            weekday = d.weekday()  # 0 = Monday, 6 = Sunday
            if weekday < 5:  # Monday to Friday (0-4)
                working_days += 1
        
        # Tính tổng giờ làm việc
        total_hours = Decimal(str(working_days * hours_per_day))
        return total_hours

    @staticmethod
    def calculate_hourly_rate(monthly_salary, year, month, hours_per_day=8):
        """
        Tính lương/giờ từ lương tháng.
        
        Args:
            monthly_salary: Lương tháng (Decimal hoặc số)
            year: Năm
            month: Tháng (1-12)
            hours_per_day: Số giờ làm việc mỗi ngày (mặc định 8)
        
        Returns:
            dict: {
                'working_hours': Decimal,
                'hourly_rate': Decimal
            }
        """
        monthly_salary = Decimal(str(monthly_salary))
        working_hours = HourlyRateService.calculate_working_hours_per_month(
            year, month, hours_per_day
        )
        
        if working_hours > 0:
            hourly_rate = monthly_salary / working_hours
        else:
            hourly_rate = Decimal('0')
        
        return {
            'working_hours': working_hours,
            'hourly_rate': hourly_rate.quantize(Decimal('0.01'))
        }

    @staticmethod
    def get_or_create_hourly_rate(employee, year, month, monthly_salary=None, hours_per_day=8, notes=''):
        """
        Lấy hoặc tạo record lương/giờ cho nhân sự trong tháng.
        
        Args:
            employee: Employee instance
            year: Năm
            month: Tháng (1-12)
            monthly_salary: Lương tháng (nếu None thì lấy từ employee.hourly_rate)
            hours_per_day: Số giờ làm việc mỗi ngày (mặc định 8)
            notes: Ghi chú
        
        Returns:
            tuple: (EmployeeHourlyRate instance, created: bool)
        """
        if monthly_salary is None:
            monthly_salary = employee.hourly_rate
        
        # Tính toán
        result = HourlyRateService.calculate_hourly_rate(
            monthly_salary, year, month, hours_per_day
        )
        
        # Lấy hoặc tạo record
        hourly_rate_obj, created = EmployeeHourlyRate.objects.get_or_create(
            employee=employee,
            month=month,
            year=year,
            defaults={
                'monthly_salary': monthly_salary,
                'working_hours_per_month': result['working_hours'],
                'hourly_rate': result['hourly_rate'],
                'notes': notes,
            }
        )
        
        # Nếu đã tồn tại nhưng lương tháng thay đổi, cập nhật
        if not created and hourly_rate_obj.monthly_salary != monthly_salary:
            hourly_rate_obj.monthly_salary = monthly_salary
            hourly_rate_obj.working_hours_per_month = result['working_hours']
            hourly_rate_obj.hourly_rate = result['hourly_rate']
            hourly_rate_obj.notes = notes
            hourly_rate_obj.save()
        
        return hourly_rate_obj, created

    @staticmethod
    def get_current_hourly_rate(employee):
        """
        Lấy lương/giờ hiện tại của nhân sự (tháng hiện tại).
        
        Args:
            employee: Employee instance
        
        Returns:
            EmployeeHourlyRate hoặc None
        """
        today = timezone.now().date()
        return EmployeeHourlyRate.objects.filter(
            employee=employee,
            year=today.year,
            month=today.month
        ).first()

    @staticmethod
    def get_hourly_rate_history(employee, limit=12):
        """
        Lấy lịch sử lương/giờ của nhân sự.
        
        Args:
            employee: Employee instance
            limit: Số tháng tối đa (mặc định 12)
        
        Returns:
            QuerySet: EmployeeHourlyRate objects
        """
        return EmployeeHourlyRate.objects.filter(
            employee=employee
        ).order_by('-year', '-month')[:limit]
