from decimal import Decimal
from typing import Dict, Iterable

from django.db.models import Count, Sum, Q
from django.utils import timezone

from core.models import Notification
from core.notification_service import NotificationService
from projects.models import DelayRuleConfig, Task
from projects.models import Project
from resources.models import Employee


class DelayKPIService:
    """Rule engine for overdue KPI, penalty/reward, and escalation."""

    EXEMPT_REASONS = {"dependency", "external", "scope_change"}

    @classmethod
    def get_active_config(cls) -> DelayRuleConfig:
        config = DelayRuleConfig.objects.filter(is_active=True).order_by("-updated_at").first()
        if config:
            return config
        return DelayRuleConfig.objects.create()

    @classmethod
    def _severity_multiplier(cls, task: Task) -> Decimal:
        return Decimal("2") if task.priority == "critical" else Decimal("1")

    @classmethod
    def _task_weight(cls, task: Task) -> Decimal:
        # Weight by estimated hours, min = 1
        hours = Decimal(task.estimated_hours or 0)
        if hours <= 0:
            return Decimal("1")
        if hours <= 8:
            return Decimal("1")
        if hours <= 24:
            return Decimal("1.25")
        return Decimal("1.5")

    @classmethod
    def _base_penalty(cls, days_late: int, config: DelayRuleConfig) -> Decimal:
        if days_late <= 0:
            return Decimal("0")
        if days_late <= 2:
            return Decimal(config.penalty_light)
        if days_late <= 5:
            return Decimal(config.penalty_medium)
        if days_late <= 10:
            return Decimal(config.penalty_heavy)
        return Decimal(config.penalty_critical)

    @classmethod
    def _should_apply_penalty(cls, task: Task) -> bool:
        project_enabled = getattr(task.project, "delay_penalty_enabled", True)
        employee_enabled = bool(task.assigned_to and task.assigned_to.delay_penalty_enabled)
        if not project_enabled or not employee_enabled:
            return False

        # dependency/external/scope_change only exempt when approved by manager.
        if task.delay_reason_type in cls.EXEMPT_REASONS and task.approved_delay:
            return False
        return True

    @classmethod
    def _compute_days_late(cls, task: Task) -> int:
        if not task.due_date:
            return 0
        end_date = None
        if task.completed_at:
            end_date = task.completed_at.date()
        elif task.status == "overdue":
            end_date = timezone.now().date()
        elif task.status == "done":
            end_date = timezone.now().date()
        if not end_date:
            return 0
        return max((end_date - task.due_date).days, 0)

    @classmethod
    def _compute_overdeliver_reward(cls, task: Task, config: DelayRuleConfig) -> Decimal:
        if task.status != "done" or not task.due_date:
            return Decimal("0")
        completed_date = task.completed_at.date() if task.completed_at else timezone.now().date()
        if completed_date > task.due_date:
            return Decimal("0")
        if task.estimated_hours and task.actual_hours and Decimal(task.actual_hours) <= Decimal(task.estimated_hours) * Decimal("0.9"):
            return Decimal(config.overdeliver_reward)
        return Decimal("0")

    @classmethod
    def update_task_delay_metrics(cls, task: Task, actor=None) -> None:
        if not task.assigned_to:
            return

        config = cls.get_active_config()
        days_late = cls._compute_days_late(task)
        task.days_late = days_late

        if task.status == "done" and not task.completed_at:
            task.completed_at = timezone.now()

        if days_late <= 0:
            task.delay_score = Decimal("0")
            task.save(update_fields=["days_late", "delay_score", "completed_at", "updated_at"])
            cls.recompute_employee_profile(task.assigned_to, actor=actor)
            return

        if not cls._should_apply_penalty(task):
            task.delay_score = Decimal("0")
        else:
            base = cls._base_penalty(days_late, config)
            task.delay_score = (base * cls._task_weight(task) * cls._severity_multiplier(task)).quantize(Decimal("0.01"))

        update_fields = ["days_late", "delay_score", "updated_at"]
        if task.completed_at:
            update_fields.append("completed_at")
        task.save(update_fields=update_fields)

        cls._send_delay_notifications(task, config, actor=actor)
        cls.recompute_employee_profile(task.assigned_to, actor=actor)

    @classmethod
    def _send_delay_notifications(cls, task: Task, config: DelayRuleConfig, actor=None) -> None:
        employee = task.assigned_to
        if not employee or not employee.user:
            return

        late_count = Task.objects.filter(
            assigned_to=employee,
            days_late__gt=0,
        ).count()

        if late_count == 1:
            NotificationService.notify(
                user=employee.user,
                title=f"Canh bao tre han: {task.name}",
                message=f"Task \"{task.name}\" dang tre {task.days_late} ngay.",
                level=Notification.LEVEL_WARNING,
                url=f"/projects/tasks/{task.pk}/edit/",
                actor=actor,
            )
        elif late_count in (2, 3):
            NotificationService.notify(
                user=employee.user,
                title=f"KPI bi tru do tre han ({late_count} lan)",
                message=f"He thong da tinh tru KPI cho task \"{task.name}\".",
                level=Notification.LEVEL_WARNING,
                url=f"/projects/tasks/{task.pk}/edit/",
                actor=actor,
            )
        else:
            manager = getattr(task.project, "created_by", None)
            if manager:
                NotificationService.notify(
                    user=manager,
                    title=f"Nhan vien tre han >3 lan: {employee.full_name}",
                    message=f"{employee.full_name} co {late_count} task tre han. Vui long xem xet.",
                    level=Notification.LEVEL_DANGER,
                    url=f"/projects/{task.project_id}/",
                    actor=actor,
                )

        if task.days_late > int(config.requires_explanation_after_days) and not (task.delay_explanation or "").strip():
            NotificationService.notify(
                user=employee.user,
                title="Yeu cau giai trinh tre han",
                message=f"Task \"{task.name}\" tre hon {config.requires_explanation_after_days} ngay. Vui long cap nhat giai trinh.",
                level=Notification.LEVEL_DANGER,
                url=f"/projects/tasks/{task.pk}/edit/",
                actor=actor,
            )

    @classmethod
    def recompute_employee_profile(cls, employee: Employee, actor=None) -> None:
        config = cls.get_active_config()
        tasks_qs = Task.objects.filter(assigned_to=employee)
        total_delay_score = tasks_qs.aggregate(total=Sum("delay_score"))["total"] or Decimal("0")
        delayed_tasks = tasks_qs.filter(days_late__gt=0).count()

        reward = cls._calculate_rewards(employee, config)
        kpi_current = (Decimal("100") - Decimal(total_delay_score) + reward).quantize(Decimal("0.01"))
        if kpi_current < 0:
            kpi_current = Decimal("0")
        if kpi_current > 100:
            kpi_current = Decimal("100")

        if total_delay_score >= 60:
            penalty_level, bonus_reduction = 3, Decimal("50")
        elif total_delay_score >= 30:
            penalty_level, bonus_reduction = 2, Decimal("25")
        elif total_delay_score > 0:
            penalty_level, bonus_reduction = 1, Decimal("10")
        else:
            penalty_level, bonus_reduction = 0, Decimal("0")

        employee.total_delay_score = Decimal(total_delay_score).quantize(Decimal("0.01"))
        employee.kpi_current = kpi_current
        employee.penalty_level = penalty_level
        employee.bonus_reduction_percent = bonus_reduction
        employee.warning_count = delayed_tasks
        employee.at_risk = kpi_current < Decimal("80")
        employee.save(
            update_fields=[
                "total_delay_score",
                "kpi_current",
                "penalty_level",
                "bonus_reduction_percent",
                "warning_count",
                "at_risk",
                "updated_at",
            ]
        )

    @classmethod
    def _calculate_rewards(cls, employee: Employee, config: DelayRuleConfig) -> Decimal:
        reward = Decimal("0")
        now = timezone.now()

        done_tasks = Task.objects.filter(assigned_to=employee, status="done", due_date__isnull=False)
        for task in done_tasks:
            if not task.completed_at:
                continue
            completed_date = task.completed_at.date()
            days_early = (task.due_date - completed_date).days
            if days_early <= 0:
                continue
            if days_early >= 3:
                reward += Decimal(config.early_completion_reward_max)
            else:
                reward += Decimal(config.early_completion_reward_min)
            reward += cls._compute_overdeliver_reward(task, config)

        month_start = now.date().replace(day=1)
        delayed_this_month = Task.objects.filter(
            assigned_to=employee,
            due_date__gte=month_start,
            days_late__gt=0,
        ).exists()
        if not delayed_this_month:
            reward += Decimal(config.no_delay_monthly_reward)

        return reward.quantize(Decimal("0.01"))

    @classmethod
    def can_assign_critical_task(cls, user) -> bool:
        employee = getattr(user, "employee", None)
        if not employee:
            return True
        return Decimal(employee.kpi_current) >= Decimal("70")

    @classmethod
    def can_approve_others(cls, user) -> bool:
        employee = getattr(user, "employee", None)
        if not employee:
            return True
        return Decimal(employee.kpi_current) >= Decimal("70")

    @classmethod
    def sync_overdue_tasks(cls, tasks: Iterable[Task], actor=None) -> int:
        now = timezone.now()
        today = now.date()
        changed = 0
        for task in tasks:
            should_overdue = False
            if task.due_date and task.due_date < today and task.status in {"todo", "in_progress", "review"}:
                should_overdue = True
            elif task.estimated_end_at and task.estimated_end_at <= now and task.status in {"todo", "in_progress", "review"}:
                should_overdue = True
            if should_overdue:
                task.status = "overdue"
                task.save(update_fields=["status", "updated_at"])
                cls.update_task_delay_metrics(task, actor=actor)
                changed += 1
        return changed

    @classmethod
    def get_accessible_employee_ids_for_manager(cls, current_user):
        if not current_user or not current_user.is_authenticated:
            return set()
        if current_user.is_superuser:
            return set(Employee.objects.filter(is_active=True).values_list("id", flat=True))

        pm_employee = Employee.objects.filter(user=current_user, is_active=True).first()
        project_filter = Q(created_by=current_user)
        if pm_employee:
            project_filter |= Q(project_manager=pm_employee)

        project_ids = list(
            Project.objects.filter(project_filter).values_list("id", flat=True).distinct()
        )
        if not project_ids:
            return {pm_employee.id} if pm_employee else set()

        related_ids = set(
            Employee.objects.filter(
                Q(assigned_tasks__project_id__in=project_ids)
                | Q(allocations__project_id__in=project_ids)
            )
            .values_list("id", flat=True)
            .distinct()
        )
        if pm_employee:
            related_ids.add(pm_employee.id)
        return related_ids

    @classmethod
    def get_dashboard_queryset(cls, current_user=None, user_id=None, project_id=None, role_name=None):
        qs = Employee.objects.filter(is_active=True).select_related("department", "user")
        if current_user and not current_user.is_superuser:
            accessible_ids = cls.get_accessible_employee_ids_for_manager(current_user)
            qs = qs.filter(id__in=accessible_ids)
        if user_id:
            qs = qs.filter(id=user_id)
        if project_id:
            qs = qs.filter(Q(assigned_tasks__project_id=project_id) | Q(allocations__project_id=project_id)).distinct()
        if role_name:
            qs = qs.filter(user__user_roles__role__name__iexact=role_name).distinct()
        return qs.order_by("-at_risk", "kpi_current", "last_name", "first_name")
