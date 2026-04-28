from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from core.rbac import get_user_role_names
from projects.models import Project, Task
from resources.models import Employee


class AIControlCenterView(LoginRequiredMixin, TemplateView):
    """Single page to access all implemented AI features by role."""

    template_name = "pages/ai_center.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_names = get_user_role_names(self.request.user)
        role_names_lc = {r.lower() for r in role_names}

        context["page_title"] = "AI Center"
        context["role_names"] = sorted(role_names)

        context["can_chat"] = True
        context["can_task_risk"] = bool(role_names.intersection({"ADMIN", "MANAGER", "EMPLOYEE"}))
        context["can_project_risk"] = bool(role_names.intersection({"ADMIN", "MANAGER"}))
        context["can_project_report"] = bool(role_names.intersection({"ADMIN", "MANAGER", "FINANCE"}))
        context["can_resource_recommend"] = bool(role_names.intersection({"ADMIN", "MANAGER"}))
        context["can_forecast"] = bool(role_names.intersection({"ADMIN", "FINANCE"}))
        context["can_anomaly"] = bool(role_names.intersection({"ADMIN", "FINANCE"}))
        context["can_attrition"] = bool(
            role_names.intersection({"ADMIN", "MANAGER"}) or bool({"hr", "hr_admin"} & role_names_lc)
        )

        is_admin = "ADMIN" in role_names or self.request.user.is_superuser or self.request.user.is_staff
        is_manager = "MANAGER" in role_names
        is_employee_role = "EMPLOYEE" in role_names

        current_employee = Employee.objects.filter(user=self.request.user).first()
        projects_qs = Project.objects.all()
        tasks_qs = Task.objects.select_related("project")
        employees_qs = Employee.objects.filter(is_active=True)
        data_scope = "Toan he thong"

        if not is_admin:
            if is_manager and current_employee:
                projects_qs = projects_qs.filter(
                    project_manager=current_employee
                ).distinct() | projects_qs.filter(
                    allocations__employee=current_employee
                ).distinct() | projects_qs.filter(
                    created_by=self.request.user
                ).distinct()
                tasks_qs = tasks_qs.filter(project__in=projects_qs).distinct()
                employees_qs = employees_qs.filter(
                    id__in=projects_qs.values_list("allocations__employee_id", flat=True)
                ).distinct()
                data_scope = "Chi du an ban quan ly"
            elif is_employee_role and current_employee:
                projects_qs = projects_qs.filter(
                    allocations__employee=current_employee
                ).distinct()
                tasks_qs = tasks_qs.filter(
                    project__in=projects_qs
                ).filter(
                    assigned_to=current_employee
                ).distinct() | tasks_qs.filter(
                    assignees=current_employee
                ).distinct()
                employees_qs = employees_qs.filter(id=current_employee.id)
                data_scope = "Chi task/du an duoc giao cho ban"
            else:
                projects_qs = projects_qs.none()
                tasks_qs = tasks_qs.none()
                employees_qs = employees_qs.none()
                data_scope = "Khong co du lieu trong pham vi role hien tai"

        context["is_admin_role"] = is_admin
        context["is_manager_role"] = is_manager and not is_admin
        context["data_scope"] = data_scope

        context["projects"] = projects_qs.order_by("name")[:200]
        context["tasks"] = tasks_qs.order_by("-created_at")[:200]
        context["employees"] = employees_qs.order_by("last_name", "first_name")[:200]
        return context
