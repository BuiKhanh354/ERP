import csv
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from core.mixins import is_employee, is_manager
from projects.models import Project, Task
from resources.models import Employee


class DelayKPIAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not (is_employee(request.user) or is_manager(request.user)):
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
        if is_manager(self.request.user):
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

        if is_manager(self.request.user):
            project_ids = self._get_managed_project_ids()
            projects = Project.objects.filter(id__in=project_ids).values("id", "name").order_by("name")
        else:
            projects = (
                Task.objects.filter(assigned_to_id__in=scope_employees.values_list("id", flat=True))
                .values("project_id", "project__name")
                .order_by("project__name")
                .distinct()
            )

        context["is_manager_view"] = is_manager(self.request.user)
        context["employees"] = scope_employees
        context["projects"] = projects
        context["selected_user"] = self.request.GET.get("user", "")
        context["selected_project"] = self.request.GET.get("project", "")
        return context


class DelayKPIDataAPIView(DelayKPIAccessMixin, View):
    def get(self, request):
        project_id = request.GET.get("project")
        user_id = request.GET.get("user")

        qs = self._get_scope_employees()

        if is_manager(request.user) and user_id:
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

        if is_manager(request.user) and user_id:
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
