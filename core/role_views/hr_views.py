from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from resources.models import Employee, Department
from projects.models import TimeEntry
from decimal import Decimal


class HRDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_EMPLOYEE_PROFILE'
    template_name = 'modules/hr/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # KPI Widgets
        context['total_employees'] = Employee.objects.filter(is_active=True).count()

        # New employees this month
        month_start = timezone.now().replace(day=1).date()
        context['new_employees_this_month'] = Employee.objects.filter(
            is_active=True,
            hire_date__gte=month_start
        ).count()

        # Contracts expiring in 30 days
        thirty_days_later = timezone.now().date() + timedelta(days=30)
        # Note: This requires a Contract model - placeholder for now
        context['contracts_expiring_soon'] = 0

        # Average salary (from hourly rate * 160 hours/month)
        avg_hourly_rate = Employee.objects.filter(
            is_active=True
        ).aggregate(avg=Avg('hourly_rate'))['avg'] or Decimal('0')
        context['average_salary'] = float(avg_hourly_rate * 160)

        # Total payroll (estimated)
        total_hours = Employee.objects.filter(is_active=True).count() * 160
        context['total_payroll'] = float(total_hours * avg_hourly_rate)

        # Department distribution
        dept_data = Department.objects.annotate(
            dept_employee_count=Count('employee', filter=Q(employee__is_active=True))
        ).order_by('-dept_employee_count')[:5]
        context['department_labels'] = [d.name for d in dept_data]
        context['department_counts'] = [d.dept_employee_count for d in dept_data]

        # Employment type distribution
        employment_types = Employee.objects.filter(
            is_active=True
        ).values('employment_type').annotate(
            count=Count('id')
        ).order_by('-count')
        context['employment_type_labels'] = [
            dict(Employee.EMPLOYMENT_TYPE_CHOICES)[item['employment_type']]
            for item in employment_types
        ]
        context['employment_type_counts'] = [item['count'] for item in employment_types]

        # Monthly hiring trend (last 6 months)
        hiring_trend = []
        for i in range(5, -1, -1):
            month_date = timezone.now() - timedelta(days=30*i)
            month_start = month_date.replace(day=1).date()
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            count = Employee.objects.filter(
                is_active=True,
                hire_date__gte=month_start,
                hire_date__lte=month_end
            ).count()
            hiring_trend.append(count)

        context['hiring_trend_labels'] = [
            (timezone.now() - timedelta(days=30*i)).strftime('%m/%Y')
            for i in range(5, -1, -1)
        ]
        context['hiring_trend_data'] = hiring_trend

        return context
