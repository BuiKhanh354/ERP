"""Scheduled tasks for projects module."""
from django.utils import timezone
from .models import Project, Task


def check_overdue_tasks():
    """Check and update overdue tasks."""
    today = timezone.now().date()
    overdue_tasks = Task.objects.filter(
        due_date__lt=today,
        status__in=['todo', 'in_progress']
    )
    return overdue_tasks

