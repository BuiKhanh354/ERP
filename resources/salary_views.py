"""
Views cho theo dõi lương của nhân viên.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Employee
from projects.models import Task, TimeEntry
from performance.models import PerformanceScore


class SalaryTrackingView(LoginRequiredMixin, TemplateView):
    """View theo dõi lương cho nhân viên."""
    template_name = 'resources/salary_tracking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Lấy employee record của user hiện tại
        try:
            employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            # Nếu không có employee record, tạo một record tạm
            employee = None
            context['has_employee_record'] = False
            return context
        
        context['has_employee_record'] = True
        context['employee'] = employee
        
        # Thông tin lương cơ bản
        context['hourly_rate'] = employee.hourly_rate
        context['employment_type'] = employee.get_employment_type_display()
        context['position'] = employee.position
        context['department'] = employee.department.name if employee.department else 'Chưa có phòng ban'
        
        # Tính lương từ TimeEntry (30 ngày gần nhất)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        time_entries = TimeEntry.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )
        
        total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or Decimal('0')
        context['total_hours_this_month'] = float(total_hours)
        context['estimated_salary_this_month'] = float(total_hours * employee.hourly_rate)
        
        # Lịch sử lương (theo tháng)
        monthly_salary = []
        for i in range(6):  # 6 tháng gần nhất
            month_start = (timezone.now() - timedelta(days=30 * i)).replace(day=1).date()
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_entries = TimeEntry.objects.filter(
                employee=employee,
                date__gte=month_start,
                date__lte=month_end
            )
            month_hours = month_entries.aggregate(total=Sum('hours'))['total'] or Decimal('0')
            month_salary_amount = float(month_hours * employee.hourly_rate)
            
            monthly_salary.append({
                'month': month_start.strftime('%Y-%m'),
                'month_display': month_start.strftime('%m/%Y'),
                'hours': float(month_hours),
                'salary': month_salary_amount,
            })
        
        context['monthly_salary'] = list(reversed(monthly_salary))
        
        # Công việc đã hoàn thành (để tính lương)
        completed_tasks = Task.objects.filter(
            assigned_to=employee,
            status='done'
        ).order_by('-updated_at')[:20]
        
        context['completed_tasks'] = completed_tasks
        context['total_completed_tasks'] = Task.objects.filter(
            assigned_to=employee,
            status='done'
        ).count()
        
        # Điểm hiệu suất (để tính thưởng)
        performance_scores = PerformanceScore.objects.filter(
            employee=employee
        ).order_by('-period_end')[:6]
        
        context['performance_scores'] = performance_scores
        from django.db.models import Avg
        avg_performance = PerformanceScore.objects.filter(
            employee=employee
        ).aggregate(avg=Avg('overall_score'))['avg'] or 0
        context['avg_performance'] = float(avg_performance)
        
        # Tính thưởng dựa trên hiệu suất (ví dụ: > 90 điểm = 10% thưởng)
        bonus_percentage = 0
        if avg_performance >= 90:
            bonus_percentage = 10
        elif avg_performance >= 80:
            bonus_percentage = 5
        elif avg_performance >= 70:
            bonus_percentage = 2
        
        context['bonus_percentage'] = bonus_percentage
        context['estimated_bonus'] = context['estimated_salary_this_month'] * (bonus_percentage / 100)
        
        # Thời gian phát lương (lấy từ PayrollSchedule chung nếu có, mặc định ngày 5)
        today = timezone.now().date()
        from .models import PayrollSchedule
        payroll_schedule = PayrollSchedule.get_active_schedule()
        
        if payroll_schedule:
            salary_date = payroll_schedule.get_next_payment_date()
            context['has_payroll_schedule'] = True
            context['payment_day'] = payroll_schedule.payment_day
        else:
            # Nếu chưa có lịch phát lương, dùng mặc định ngày 5
            if today.day < 5:
                salary_date = today.replace(day=5)
            else:
                if today.month == 12:
                    salary_date = today.replace(year=today.year + 1, month=1, day=5)
                else:
                    salary_date = today.replace(month=today.month + 1, day=5)
            context['has_payroll_schedule'] = False
            context['payment_day'] = 5
        
        context['next_salary_date'] = salary_date
        context['days_until_salary'] = (salary_date - today).days
        
        # Lịch sử TimeEntry gần đây (với salary đã tính sẵn)
        recent_entries = time_entries.select_related('task', 'task__project').order_by('-date')[:10]
        # Tính salary cho mỗi entry
        entries_with_salary = []
        for entry in recent_entries:
            entry_salary = float(entry.hours * employee.hourly_rate)
            entries_with_salary.append({
                'entry': entry,
                'salary': entry_salary,
            })
        context['recent_time_entries'] = entries_with_salary
        
        return context
