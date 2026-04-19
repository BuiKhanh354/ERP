from django.db.models import Count, Q
from django.contrib import messages
from django.views.generic import TemplateView
from django.shortcuts import redirect

from core.models import UserRole
from core.rbac import PermissionRequiredMixin
from projects.models import Project, Task
from resources.models import Employee, ResourceAllocation, EmployeeSkill

class PMDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_PROJECT'
    template_name = 'modules/pm/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        pm_employee = (
            Employee.objects.select_related("department", "user")
            .filter(user=user, is_active=True)
            .first()
        )

        project_filter = Q(created_by=user)
        if pm_employee:
            project_filter |= Q(project_manager=pm_employee)

        managed_projects = (
            Project.objects.filter(project_filter)
            .select_related("client", "project_manager__user")
            .distinct()
            .order_by("-created_at")
        )
        project_ids = list(managed_projects.values_list("id", flat=True))

        task_assignee_ids = set()
        allocation_employee_ids = set()
        dept_manager_ids = set()

        if project_ids:
            task_assignee_ids = set(
                Task.objects.filter(project_id__in=project_ids, assigned_to__isnull=False)
                .values_list("assigned_to_id", flat=True)
            )
            allocation_employee_ids = set(
                Employee.objects.filter(allocations__project_id__in=project_ids)
                .values_list("id", flat=True)
            )
            dept_manager_ids = set(
                Employee.objects.filter(
                    Q(managed_departments__projects__id__in=project_ids)
                    | Q(managed_departments__required_projects__id__in=project_ids)
                ).values_list("id", flat=True)
            )

        related_employee_ids = set()
        if pm_employee:
            related_employee_ids.add(pm_employee.id)
        related_employee_ids.update(task_assignee_ids)
        related_employee_ids.update(allocation_employee_ids)
        related_employee_ids.update(dept_manager_ids)

        related_employees = (
            Employee.objects.select_related("user", "department")
            .filter(id__in=related_employee_ids, is_active=True)
            .order_by("last_name", "first_name")
        )

        role_map = {}
        user_ids = [emp.user_id for emp in related_employees if emp.user_id]
        if user_ids:
            for row in UserRole.objects.filter(user_id__in=user_ids).select_related("role"):
                role_map.setdefault(row.user_id, []).append(row.role.name)

        related_accounts = []
        for employee in related_employees:
            relation_types = []
            if pm_employee and employee.id == pm_employee.id:
                relation_types.append("Project Manager")
            if employee.id in task_assignee_ids:
                relation_types.append("Task assignee")
            if employee.id in allocation_employee_ids:
                relation_types.append("Resource allocation")
            if employee.id in dept_manager_ids:
                relation_types.append("Department manager")

            related_accounts.append(
                {
                    "employee_id": employee.employee_id,
                    "full_name": employee.full_name,
                    "username": employee.user.username if employee.user else None,
                    "department": employee.department.name if employee.department else "Chưa có phòng ban",
                    "roles": role_map.get(employee.user_id, []),
                    "relations": relation_types or ["Project related"],
                }
            )

        context["pm_employee"] = pm_employee
        context["managed_projects"] = managed_projects[:8]
        context["managed_projects_count"] = managed_projects.count()
        context["active_tasks_count"] = (
            Task.objects.filter(project_id__in=project_ids).exclude(status="done").count()
            if project_ids
            else 0
        )

        # Charts: project status distribution
        project_status_rows = (
            managed_projects.order_by()
            .values("status")
            .annotate(count=Count("id"))
        )
        status_map = {row["status"]: row["count"] for row in project_status_rows}
        context["pm_project_status_labels"] = ["Planning", "Active", "On Hold", "Completed", "Cancelled"]
        context["pm_project_status_data"] = [
            status_map.get("planning", 0),
            status_map.get("active", 0),
            status_map.get("on_hold", 0),
            status_map.get("completed", 0),
            status_map.get("cancelled", 0),
        ]

        # Charts: project progress (%)
        chart_projects = list(managed_projects[:8])
        context["pm_progress_labels"] = [p.name[:20] for p in chart_projects]
        context["pm_progress_data"] = [round(float(p.calculated_progress or 0), 2) for p in chart_projects]

        # Charts: task status distribution
        task_status_rows = (
            Task.objects.filter(project_id__in=project_ids)
            .order_by()
            .values("status")
            .annotate(count=Count("id"))
        ) if project_ids else []
        task_status_map = {row["status"]: row["count"] for row in task_status_rows}
        context["pm_task_status_labels"] = ["To Do", "In Progress", "Review", "Done", "Overdue"]
        context["pm_task_status_data"] = [
            task_status_map.get("todo", 0),
            task_status_map.get("in_progress", 0),
            task_status_map.get("review", 0),
            task_status_map.get("done", 0),
            task_status_map.get("overdue", 0),
        ]

        # Charts: workload by assignee
        assignee_rows = (
            Task.objects.filter(project_id__in=project_ids, assigned_to__isnull=False)
            .order_by()
            .values("assigned_to__first_name", "assigned_to__last_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        ) if project_ids else []
        context["pm_member_labels"] = [
            f"{row['assigned_to__first_name']} {row['assigned_to__last_name']}".strip()
            for row in assignee_rows
        ]
        context["pm_member_task_data"] = [row["count"] for row in assignee_rows]

        context["related_accounts"] = related_accounts
        context["related_accounts_count"] = len(related_accounts)
        return context


class PMRequestMemberView(PermissionRequiredMixin, TemplateView):
    """PM is not allowed to add/request members."""

    template_name = 'modules/projects/pages/project_request_member.html'
    permission_required = 'VIEW_ALL_PROJECTS'

    def get(self, request, *args, **kwargs):
        messages.error(request, 'PM khong co quyen them nhan vien vao du an.')
        return redirect('projects:list')

    def post(self, request, *args, **kwargs):
        messages.error(request, 'PM khong co quyen them nhan vien vao du an.')
        return redirect('projects:list')

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class PMMemberApprovalView(PermissionRequiredMixin, TemplateView):
    """PM can remove project members, but cannot add members."""

    template_name = 'modules/projects/pages/project_member_approval.html'
    permission_required = 'VIEW_ALL_PROJECTS'

    def post(self, request, *args, **kwargs):
        project_id = kwargs.get('project_id')
        project = Project.objects.filter(pk=project_id).first()
        if not project:
            messages.error(request, 'Project not found.')
            return redirect('projects:member_approval', project_id=project_id)

        allocation_id = request.POST.get('allocation_id')
        action = request.POST.get('action')

        allocation = ResourceAllocation.objects.filter(
            pk=allocation_id,
            project=project,
        ).select_related('employee').first()
        if not allocation:
            messages.error(request, 'Khong tim thay thanh vien trong du an.')
            return redirect('projects:member_approval', project_id=project.id)

        if action == 'remove_member':
            employee_name = allocation.employee.full_name
            allocation.delete()
            messages.success(request, f'PM da loai {employee_name} khoi du an.')
            return redirect('projects:member_approval', project_id=project.id)

        messages.warning(request, 'Hanh dong khong hop le.')
        return redirect('projects:member_approval', project_id=project.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = kwargs.get('project_id')
        project = Project.objects.filter(pk=project_id).first()

        if not project:
            context['error'] = 'Project not found'
            return context

        allocations = ResourceAllocation.objects.filter(project=project).select_related('employee__department')
        members = []
        for allocation in allocations:
            employee = allocation.employee
            skills = EmployeeSkill.objects.filter(employee=employee).select_related('skill').order_by('-proficiency')
            members.append(
                {
                    'employee': employee,
                    'allocation': allocation,
                    'skills': skills,
                }
            )

        context.update({'project': project, 'members': members})
        return context
