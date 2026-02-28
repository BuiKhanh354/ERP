"""Project business logic services."""
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import Project, Task, TimeEntry
from core.models import Notification


class ProjectService:
    """Service class for project-related operations."""

    @staticmethod
    def get_project_summary(project_id):
        """Get comprehensive summary for a project."""
        project = Project.objects.get(id=project_id)
        tasks = Task.objects.filter(project=project)
        time_entries = TimeEntry.objects.filter(task__project=project)
        
        total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
        completed_tasks = tasks.filter(status='done').count()
        total_tasks = tasks.count()
        
        return {
            'project': project,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'total_hours': total_hours,
            'budget_utilization': (project.actual_budget / project.estimated_budget * 100) if project.estimated_budget > 0 else 0,
        }

    @staticmethod
    def get_active_projects():
        """Get all active projects."""
        return Project.objects.filter(status='active')

    @staticmethod
    def get_projects_by_status(status):
        """Get projects filtered by status."""
        return Project.objects.filter(status=status)


class TaskNotificationService:
    """Sinh thông báo cho công việc đến hạn/quá hạn/sắp hết giờ ước tính."""

    @staticmethod
    def _notify_once(user, title, message, level=Notification.LEVEL_INFO, url=""):
        # Tránh spam: nếu cùng title đã tạo trong 6 giờ gần nhất thì bỏ qua
        since = timezone.now() - timedelta(hours=6)
        if Notification.objects.filter(user=user, title=title, created_at__gte=since).exists():
            return
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            level=level,
            url=url or "",
            created_by=user,
        )

    @staticmethod
    def sync_for_user(user):
        """Sync thông báo cho user hiện tại (nhẹ, giới hạn số lượng)."""
        if not user or not user.is_authenticated:
            return

        profile = getattr(user, "profile", None)
        is_manager = bool(profile and profile.is_manager())
        now = timezone.now()
        today = now.date()

        employee = getattr(user, "employee", None)
        if is_manager:
            base_qs = Task.objects.exclude(status="done").select_related("project")
        else:
            if employee:
                base_qs = Task.objects.filter(assigned_to=employee).exclude(status="done").select_related("project")
            else:
                base_qs = Task.objects.filter(project__created_by=user).exclude(status="done").select_related("project")

        # 1) Đến hạn / quá hạn theo due_date
        overdue_due = base_qs.filter(due_date__lt=today)[:20]
        for t in overdue_due:
            url = f"/projects/tasks/?project={t.project_id}"
            TaskNotificationService._notify_once(
                user=user,
                title=f"Công việc quá hạn: {t.name}",
                message=f"Công việc \"{t.name}\" (Dự án: {t.project.name}) đã quá hạn và chưa hoàn thành.",
                level=Notification.LEVEL_DANGER,
                url=url,
            )

        due_soon = base_qs.filter(due_date__gte=today, due_date__lte=today + timedelta(days=1))[:20]
        for t in due_soon:
            url = f"/projects/tasks/?project={t.project_id}"
            TaskNotificationService._notify_once(
                user=user,
                title=f"Công việc sắp đến hạn: {t.name}",
                message=f"Công việc \"{t.name}\" (Dự án: {t.project.name}) sắp đến hạn. Hãy thực hiện ngay.",
                level=Notification.LEVEL_WARNING,
                url=url,
            )

        # 2) Sắp hết giờ ước tính / quá giờ ước tính (theo started_at + estimated_hours)
        # Chỉ xét task đã bắt đầu và có giờ ước tính
        est_qs = base_qs.filter(started_at__isnull=False).exclude(estimated_hours__lte=0)
        # Lấy một batch nhỏ, tính ở Python để tránh phụ thuộc DB
        for t in est_qs.order_by("-started_at")[:50]:
            end_at = t.estimated_end_at
            if not end_at:
                continue
            url = f"/projects/tasks/?project={t.project_id}"
            if end_at <= now:
                TaskNotificationService._notify_once(
                    user=user,
                    title=f"Công việc quá giờ ước tính: {t.name}",
                    message=f"Công việc \"{t.name}\" (Dự án: {t.project.name}) đã quá giờ ước tính và chưa hoàn thành.",
                    level=Notification.LEVEL_DANGER,
                    url=url,
                )
            elif end_at <= now + timedelta(minutes=30):
                mins = int((end_at - now).total_seconds() // 60)
                TaskNotificationService._notify_once(
                    user=user,
                    title=f"Công việc sắp hết giờ ước tính: {t.name}",
                    message=f"Công việc \"{t.name}\" (Dự án: {t.project.name}) sắp hết giờ ước tính (còn ~{mins} phút). Hãy thực hiện ngay.",
                    level=Notification.LEVEL_WARNING,
                    url=url,
                )

