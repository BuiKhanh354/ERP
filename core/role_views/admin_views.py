from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q
from core.rbac import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from resources.models import Employee, ResourceAllocation, EmployeeSkill
from projects.models import Project, ProjectMembershipRequest


class AdminDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'modules/admin/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from resources.models import Department, Employee
        from projects.models import Project, Task
        from core.models import AuditLog

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        # KPI Stats
        ctx['total_users'] = User.objects.filter(is_active=True).count()
        ctx['total_employees'] = Employee.objects.filter(is_active=True).count()
        ctx['total_departments'] = Department.objects.count()
        ctx['active_departments'] = Department.objects.filter(is_active=True).count()
        ctx['total_projects'] = Project.objects.count()

        # New users this month
        ctx['new_users_month'] = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()

        # Recent audit logs
        try:
            ctx['recent_logs'] = AuditLog.objects.select_related('user').order_by(
                '-created_at'
            )[:10]
        except Exception:
            ctx['recent_logs'] = []

        # Active tasks
        try:
            ctx['active_tasks'] = Task.objects.exclude(status='done').count()
            ctx['completed_tasks_week'] = Task.objects.filter(
                status='done', updated_at__gte=seven_days_ago
            ).count()
        except Exception:
            ctx['active_tasks'] = 0
            ctx['completed_tasks_week'] = 0

        # Recent departments
        ctx['recent_departments'] = Department.objects.order_by('-created_at')[:5]

        # Online users (logged in within last 30 min — approximate)
        ctx['online_users'] = User.objects.filter(
            last_login__gte=now - timedelta(minutes=30)
        ).count()

        return ctx


class AdminProjectMembersView(PermissionRequiredMixin, TemplateView):
    """Admin can review project members and their skills."""

    template_name = 'modules/admin/pages/project_members.html'
    permission_required = ['VIEW_USER_LIST', 'RESOURCE_ALLOCATE']

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


class AdminAddProjectMemberView(PermissionRequiredMixin, TemplateView):
    """Admin can add project members and review/approve PM requests."""

    template_name = 'modules/admin/pages/add_project_member.html'
    permission_required = ['VIEW_USER_LIST', 'RESOURCE_ALLOCATE']

    def _current_namespace(self):
        return getattr(getattr(self.request, 'resolver_match', None), 'namespace', None) or 'admin_module'

    def _redirect_add_member(self, project_id):
        return redirect(f'{self._current_namespace()}:add_project_member', project_id=project_id)

    def _redirect_project_members(self, project_id):
        return redirect(f'{self._current_namespace()}:project_members', project_id=project_id)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        project_id = kwargs.get('project_id')
        project = Project.objects.filter(pk=project_id).first()

        if not project:
            messages.error(request, 'Project not found.')
            return self._redirect_add_member(project_id)

        if action == 'add_member':
            return self._add_member(request, project)
        if action == 'approve_request':
            return self._approve_request(request, project)
        if action == 'reject_request':
            return self._reject_request(request, project)

        messages.warning(request, 'Hanh dong khong hop le.')
        return self._redirect_add_member(project.id)

    def _add_member(self, request, project):
        employee_id = request.POST.get('employee_id')
        allocation_percentage = request.POST.get('allocation_percentage') or 100
        notes = request.POST.get('notes', '').strip()

        employee = Employee.objects.filter(pk=employee_id, is_active=True).first()
        if not employee:
            messages.error(request, 'Nhan vien khong ton tai hoac khong con hoat dong.')
            return self._redirect_add_member(project.id)

        try:
            ResourceAllocation.objects.create(
                employee=employee,
                project=project,
                allocation_percentage=allocation_percentage,
                start_date=project.start_date or timezone.localdate(),
                end_date=project.end_date,
                notes=notes,
                created_by=request.user,
                updated_by=request.user,
            )
        except IntegrityError:
            messages.warning(request, f'{employee.full_name} da co phan bo trong du an nay o moc thoi gian trung lap.')
            return self._redirect_add_member(project.id)

        messages.success(request, f'Da them {employee.full_name} vao du an.')
        return self._redirect_project_members(project.id)

    def _approve_request(self, request, project):
        request_id = request.POST.get('request_id')
        allocation_percentage = request.POST.get('allocation_percentage') or 100
        admin_response = request.POST.get('admin_response', '').strip()

        membership_request = ProjectMembershipRequest.objects.filter(
            pk=request_id,
            project=project,
            status='pending',
        ).select_related('employee').first()

        if not membership_request:
            messages.error(request, 'Khong tim thay request cho phe duyet.')
            return self._redirect_add_member(project.id)

        try:
            ResourceAllocation.objects.create(
                employee=membership_request.employee,
                project=project,
                allocation_percentage=allocation_percentage,
                start_date=project.start_date or timezone.localdate(),
                end_date=project.end_date,
                notes=f'Approved from PM request. {admin_response}'.strip(),
                created_by=request.user,
                updated_by=request.user,
            )
        except IntegrityError:
            messages.warning(request, 'Nhan vien da co phan bo trong du an nay.')
            return self._redirect_add_member(project.id)

        membership_request.status = 'approved'
        membership_request.admin_response = admin_response
        membership_request.updated_by = request.user
        membership_request.save(update_fields=['status', 'admin_response', 'updated_by', 'updated_at'])

        messages.success(request, f'Da phe duyet request va them {membership_request.employee.full_name} vao du an.')
        return self._redirect_add_member(project.id)

    def _reject_request(self, request, project):
        request_id = request.POST.get('request_id')
        admin_response = request.POST.get('admin_response', '').strip()

        membership_request = ProjectMembershipRequest.objects.filter(
            pk=request_id,
            project=project,
            status='pending',
        ).first()

        if not membership_request:
            messages.error(request, 'Khong tim thay request cho tu choi.')
            return self._redirect_add_member(project.id)

        membership_request.status = 'rejected'
        membership_request.admin_response = admin_response
        membership_request.updated_by = request.user
        membership_request.save(update_fields=['status', 'admin_response', 'updated_by', 'updated_at'])

        messages.success(request, 'Da tu choi request thanh vien.')
        return self._redirect_add_member(project.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = kwargs.get('project_id')

        project = Project.objects.filter(pk=project_id).first()
        if not project:
            context['error'] = 'Project not found'
            return context

        pending_requests = ProjectMembershipRequest.objects.filter(
            project=project,
            status='pending',
        ).select_related('employee', 'requested_by')

        today = timezone.localdate()
        existing_employee_ids = ResourceAllocation.objects.filter(
            project=project
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).values_list('employee_id', flat=True)
        available_employees = Employee.objects.filter(is_active=True).exclude(id__in=existing_employee_ids).select_related('department')

        employees_with_skills = []
        for employee in available_employees:
            skills = EmployeeSkill.objects.filter(employee=employee).select_related('skill').order_by('-proficiency')
            employees_with_skills.append({'employee': employee, 'skills': skills})

        context.update(
            {
                'project': project,
                'all_projects': Project.objects.order_by('name'),
                'pending_requests': pending_requests,
                'employees_with_skills': employees_with_skills,
            }
        )
        return context
