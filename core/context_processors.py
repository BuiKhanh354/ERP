from .models import UserProfile
from projects.models import Task
from django.utils import timezone
from datetime import timedelta
from projects.services import TaskNotificationService


def user_profile(request):
    """
    Cung cấp user_profile cho mọi template.
    Tránh lỗi RelatedObjectDoesNotExist khi truy cập user.profile trong template.
    """

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"user_profile": None, "pending_tasks_count": 0}

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Sync notifications (throttle để tránh nặng)
    try:
        last = request.session.get("erp_last_notif_sync")
        now_ts = timezone.now().timestamp()
        if not last or (now_ts - float(last)) >= 60:
            TaskNotificationService.sync_for_user(request.user)
            request.session["erp_last_notif_sync"] = now_ts
    except Exception:
        # Không chặn render nếu sync lỗi
        pass
    
    # Đếm số công việc chưa hoàn thành cho sidebar badge
    is_manager = profile.is_manager()
    if is_manager:
        pending_tasks_count = Task.objects.exclude(status='done').count()
    else:
        # Nhân viên chỉ đếm công việc được gán cho mình hoặc của projects do mình tạo
        from resources.models import Employee
        employee = None
        if hasattr(request.user, 'employee'):
            employee = request.user.employee
        
        if employee:
            pending_tasks_count = Task.objects.filter(
                assigned_to=employee
            ).exclude(status='done').count()
        else:
            pending_tasks_count = Task.objects.filter(
                project__created_by=request.user
            ).exclude(status='done').count()
    
    return {
        "user_profile": profile,
        "pending_tasks_count": pending_tasks_count
    }

