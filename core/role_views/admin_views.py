from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class AdminDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'modules/admin/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from resources.models import Department, Employee
        from projects.models import Project, Task
        from core.models import AuditLog

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        # KPI Stats
        ctx['total_users'] = User.objects.filter(is_active=True).count()
        ctx['total_employees'] = Employee.objects.filter(is_active=True).count()
        ctx['total_departments'] = Department.objects.count()
        ctx['active_departments'] = Department.objects.filter(is_active=True).count()
        ctx['total_projects'] = Project.objects.count()

        # New users this month
        ctx['new_users_month'] = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()

        # Recent audit logs
        try:
            ctx['recent_logs'] = AuditLog.objects.select_related('user').order_by(
                '-created_at'
            )[:10]
        except Exception:
            ctx['recent_logs'] = []

        # Active tasks
        try:
            ctx['active_tasks'] = Task.objects.exclude(status='done').count()
            ctx['completed_tasks_week'] = Task.objects.filter(
                status='done', updated_at__gte=seven_days_ago
            ).count()
        except Exception:
            ctx['active_tasks'] = 0
            ctx['completed_tasks_week'] = 0

        # Recent departments
        ctx['recent_departments'] = Department.objects.order_by('-created_at')[:5]

        # Online users (logged in within last 30 min — approximate)
        ctx['online_users'] = User.objects.filter(
            last_login__gte=now - timedelta(minutes=30)
        ).count()

        return ctx
