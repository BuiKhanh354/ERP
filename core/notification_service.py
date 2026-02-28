"""
Service tạo Notification cho user (dùng cho UI bell + modal).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from core.models import Notification


class NotificationService:
    """Helper tạo thông báo có chống spam (dedupe theo title trong khoảng thời gian)."""

    @staticmethod
    def notify(
        *,
        user,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        url: str = "",
        actor=None,
        dedupe_minutes: int = 2,
    ) -> None:
        if not user:
            return

        since = timezone.now() - timedelta(minutes=max(0, int(dedupe_minutes)))
        if dedupe_minutes > 0 and Notification.objects.filter(
            user=user, title=title, created_at__gte=since
        ).exists():
            return

        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            level=level,
            url=url or "",
            created_by=actor or user,
            updated_by=actor or user,
        )

