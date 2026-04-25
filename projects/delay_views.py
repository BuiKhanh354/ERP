import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.rbac import get_user_role_names
from projects.delay_kpi_service import DelayKPIService
from projects.models import Project, Task, TaskDelayScoreLog, KPIAdjustmentRequest
from resources.models import Employee


def _role_names(user):
    return get_user_role_names(user)


def _is_admin(user):
    return "ADMIN" in _role_names(user) or user.is_superuser


def _is_manager(user):
    return bool(_role_names(user).intersection({"MANAGER", "ADMIN"})) or user.is_superuser


def _is_employee(user):
    return "EMPLOYEE" in _role_names(user)


class DelayKPIAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not (_is_employee(request.user) or _is_manager(request.user) or _is_admin(request.user)):
            raise PermissionDenied("Only employee or manager can access this page.")
        return super().dispatch(request, *args, **kwargs)

    def _get_current_employee(self):
        return Employee.objects.filter(user=self.request.user, is_active=True).first()

    def _get_managed_project_ids(self):
        current_employee = self._get_current_employee()
        project_filter = Q(created_by=self.request.user)
        if current_employee:
            project_filter |= Q(project_manager=current_employee)
        return list(
            Project.objects.filter(project_filter)
            .values_list("id", flat=True)
            .distinct()
        )

    def _get_scope_employees(self):
        if _is_admin(self.request.user):
            return Employee.objects.filter(is_active=True)

        if _is_manager(self.request.user):
            project_ids = self._get_managed_project_ids()
            if not project_ids:
                return Employee.objects.none()
            return (
                Employee.objects.filter(is_active=True)
                .filter(
                    Q(allocations__project_id__in=project_ids)
                    | Q(assigned_tasks__project_id__in=project_ids)
                )
                .distinct()
            )

        current_employee = self._get_current_employee()
        if not current_employee:
            return Employee.objects.none()
        return Employee.objects.filter(id=current_employee.id)


class DelayKPIDashboardView(DelayKPIAccessMixin, TemplateView):
    template_name = "projects/delay_kpi_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope_employees = self._get_scope_employees().order_by("last_name", "first_name")

        if _is_admin(self.request.user):
            projects = Project.objects.all().values("id", "name").order_by("name")
        elif _is_manager(self.request.user):
            project_ids = self._get_managed_project_ids()
            projects = Project.objects.filter(id__in=project_ids).values("id", "name").order_by("name")
        else:
            projects = (
                Task.objects.filter(assigned_to_id__in=scope_employees.values_list("id", flat=True))
                .values("project_id", "project__name")
                .order_by("project__name")
                .distinct()
            )

        context["is_manager_view"] = _is_manager(self.request.user)
        context["is_admin_view"] = _is_admin(self.request.user)
        context["is_employee_view"] = _is_employee(self.request.user)
        context["employees"] = scope_employees
        context["projects"] = projects
        context["selected_user"] = self.request.GET.get("user", "")
        context["selected_project"] = self.request.GET.get("project", "")
        context["my_pending_adjustments"] = KPIAdjustmentRequest.objects.filter(
            requested_by=self.request.user,
            status=KPIAdjustmentRequest.STATUS_PENDING,
        ).select_related("employee")[:10]
        if _is_admin(self.request.user):
            context["pending_adjustments"] = KPIAdjustmentRequest.objects.filter(
                status=KPIAdjustmentRequest.STATUS_PENDING
            ).select_related("employee", "requested_by")[:20]
        else:
            context["pending_adjustments"] = []
        return context


class DelayKPIDataAPIView(DelayKPIAccessMixin, View):
    def get(self, request):
        project_id = request.GET.get("project")
        user_id = request.GET.get("user")

        qs = self._get_scope_employees()

        if _is_manager(request.user) and user_id:
            qs = qs.filter(id=user_id)

        if project_id:
            qs = qs.filter(
                Q(assigned_tasks__project_id=project_id)
                | Q(allocations__project_id=project_id)
            ).distinct()

        rows = []
        for emp in qs.order_by("last_name", "first_name"):
            delayed_qs = Task.objects.filter(assigned_to=emp, days_late__gt=0)
            if project_id:
                delayed_qs = delayed_qs.filter(project_id=project_id)
            rows.append(
                {
                    "employee_id": emp.id,
                    "employee_name": emp.full_name,
                    "department": emp.department.name if emp.department else "",
                    "kpi_current": float(emp.kpi_current or 0),
                    "total_delay_score": float(emp.total_delay_score or 0),
                    "delayed_tasks": delayed_qs.count(),
                    "penalty_level": emp.penalty_level,
                    "bonus_reduction_percent": float(emp.bonus_reduction_percent or 0),
                    "warning_count": emp.warning_count,
                    "at_risk": bool(emp.at_risk),
                }
            )

        return JsonResponse({"rows": rows, "count": len(rows)})


class DelayKPIExportCSVView(DelayKPIAccessMixin, View):
    def get(self, request):
        project_id = request.GET.get("project")
        user_id = request.GET.get("user")

        qs = self._get_scope_employees()

        if _is_manager(request.user) and user_id:
            qs = qs.filter(id=user_id)

        if project_id:
            qs = qs.filter(
                Q(assigned_tasks__project_id=project_id)
                | Q(allocations__project_id=project_id)
            ).distinct()

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="delay_kpi_dashboard.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "employee_id",
                "employee_name",
                "department",
                "kpi_current",
                "total_delay_score",
                "delayed_tasks",
                "penalty_level",
                "bonus_reduction_percent",
                "warning_count",
                "at_risk",
            ]
        )

        for emp in qs.order_by("last_name", "first_name"):
            delayed_qs = Task.objects.filter(assigned_to=emp, days_late__gt=0)
            if project_id:
                delayed_qs = delayed_qs.filter(project_id=project_id)
            writer.writerow(
                [
                    emp.employee_id,
                    emp.full_name,
                    emp.department.name if emp.department else "",
                    Decimal(emp.kpi_current or 0),
                    Decimal(emp.total_delay_score or 0),
                    delayed_qs.count(),
                    emp.penalty_level,
                    Decimal(emp.bonus_reduction_percent or 0),
                    emp.warning_count,
                    "yes" if emp.at_risk else "no",
                ]
            )
        return response


class MyDelayHistoryAPIView(DelayKPIAccessMixin, View):
    """Nhan vien xem lich su bi tru diem theo task cua chinh minh."""

    def get(self, request):
        current_employee = Employee.objects.filter(user=request.user, is_active=True).first()
        if not current_employee:
            return JsonResponse({"employee": None, "rows": [], "count": 0})

        qs = TaskDelayScoreLog.objects.filter(employee=current_employee).select_related("task", "task__project")[:100]
        rows = []
        for row in qs:
            rows.append(
                {
                    "task_id": row.task_id,
                    "task_name": row.task.name,
                    "project_name": row.task.project.name,
                    "delta_delay_score": float(row.delta_delay_score or 0),
                    "new_delay_score": float(row.new_delay_score or 0),
                    "created_at": timezone.localtime(row.created_at).strftime("%d/%m/%Y %H:%M"),
                    "reason": row.reason or "",
                }
            )
        return JsonResponse(
            {
                "employee": {
                    "id": current_employee.id,
                    "name": current_employee.full_name,
                    "kpi_current": float(current_employee.kpi_current or 0),
                    "total_delay_score": float(current_employee.total_delay_score or 0),
                },
                "rows": rows,
                "count": len(rows),
            }
        )


class KPIAdjustmentRequestCreateView(DelayKPIAccessMixin, View):
    """Manager/Admin tao de xuat dieu chinh KPI."""

    def post(self, request):
        if not _is_manager(request.user):
            raise PermissionDenied("Only manager/admin can submit KPI adjustment request.")

        employee_id = request.POST.get("employee_id")
        points_raw = request.POST.get("points")
        reason = (request.POST.get("reason") or "").strip()
        if not employee_id or not points_raw or not reason:
            messages.error(request, "Vui long nhap day du nhan su, diem dieu chinh va ly do.")
            return redirect(reverse("projects:delay_kpi_dashboard"))

        employee = Employee.objects.filter(id=employee_id, is_active=True).first()
        if not employee:
            messages.error(request, "Khong tim thay nhan su.")
            return redirect(reverse("projects:delay_kpi_dashboard"))

        try:
            points = Decimal(points_raw)
        except Exception:
            messages.error(request, "Diem dieu chinh khong hop le.")
            return redirect(reverse("projects:delay_kpi_dashboard"))

        KPIAdjustmentRequest.objects.create(
            employee=employee,
            points=points,
            reason=reason,
            requested_by=request.user,
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, "Da gui de xuat dieu chinh KPI. Cho Admin phe duyet.")
        return redirect(reverse("projects:delay_kpi_dashboard"))


class KPIAdjustmentRequestReviewView(DelayKPIAccessMixin, View):
    """Admin duyet/tu choi de xuat KPI."""

    def post(self, request, pk):
        if not _is_admin(request.user):
            raise PermissionDenied("Only admin can review KPI adjustment request.")

        adjustment = KPIAdjustmentRequest.objects.select_related("employee").filter(pk=pk).first()
        if not adjustment:
            messages.error(request, "Khong tim thay de xuat.")
            return redirect(reverse("projects:delay_kpi_dashboard"))
        if adjustment.status != KPIAdjustmentRequest.STATUS_PENDING:
            messages.warning(request, "De xuat nay da duoc xu ly truoc do.")
            return redirect(reverse("projects:delay_kpi_dashboard"))

        action = request.POST.get("action")
        review_note = (request.POST.get("review_note") or "").strip()

        if action == "approve":
            adjustment.status = KPIAdjustmentRequest.STATUS_APPROVED
            adjustment.reviewed_by = request.user
            adjustment.review_note = review_note
            adjustment.reviewed_at = timezone.now()
            adjustment.updated_by = request.user
            adjustment.save(update_fields=["status", "reviewed_by", "review_note", "reviewed_at", "updated_by", "updated_at"])
            DelayKPIService.recompute_employee_profile(adjustment.employee, actor=request.user)
            messages.success(request, "Da phe duyet dieu chinh KPI.")
            return redirect(reverse("projects:delay_kpi_dashboard"))

        adjustment.status = KPIAdjustmentRequest.STATUS_REJECTED
        adjustment.reviewed_by = request.user
        adjustment.review_note = review_note
        adjustment.reviewed_at = timezone.now()
        adjustment.updated_by = request.user
        adjustment.save(update_fields=["status", "reviewed_by", "review_note", "reviewed_at", "updated_by", "updated_at"])
        messages.info(request, "Da tu choi de xuat dieu chinh KPI.")
        return redirect(reverse("projects:delay_kpi_dashboard"))
