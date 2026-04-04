"""Scheduled tasks for projects module."""
from django.utils import timezone
from .models import Project, Task
from .delay_kpi_service import DelayKPIService


def check_overdue_tasks():
    """Check and update overdue tasks."""
    candidates = Task.objects.filter(
        status__in=['todo', 'in_progress', 'review', 'overdue']
    ).select_related('project', 'assigned_to')
    DelayKPIService.sync_overdue_tasks(candidates)
    return candidates.filter(status='overdue')

