"""
Custom Admin Views — System Administration Only.
Theo fixgiaodien.md: User, Role, Department, Project Access, Audit, Settings.
Admin KHÔNG truy cập dữ liệu nghiệp vụ (Projects, Tasks, Clients, Budgets, HR, etc.).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils import timezone
import json

from resources.models import Department
from resources.forms import DepartmentForm


def is_staff_user(user):
    """Kiểm tra user có phải staff không."""
    return user.is_authenticated and user.is_staff


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin yêu cầu user phải là staff."""
    def test_func(self):
        return is_staff_user(self.request.user)


class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Trang dashboard admin — System Overview, Security, Activity, Recent Audit."""
    template_name = 'admin_custom/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import AuditLog, Role, UserRole
        
        # System Overview
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        context['inactive_users'] = User.objects.filter(is_active=False).count()
        now = timezone.now()
        context['new_users_this_month'] = User.objects.filter(
            date_joined__year=now.year, date_joined__month=now.month
        ).count()
        
        # System Activity (today)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_logs = AuditLog.objects.filter(created_at__gte=today_start)
        context['users_created_today'] = today_logs.filter(
            action_type='CREATE', table_name='auth_user'
        ).count()
        context['roles_changed_today'] = today_logs.filter(
            action_type='UPDATE', table_name='auth_user'
        ).count()
        context['accounts_deactivated_today'] = today_logs.filter(
            action_type='UPDATE', table_name='auth_user',
            new_data__contains='false'
        ).count()
        
        # System-level counts only (no business data)
        context['total_roles'] = Role.objects.filter(is_active=True).count()
        context['total_departments'] = Department.objects.count()
        
        # Security metrics
        context['failed_login_attempts'] = AuditLog.objects.filter(
            action_type='LOGIN_FAILED'
        ).filter(created_at__gte=today_start).count()
        
        # Recent Audit Logs
        context['recent_audit'] = AuditLog.objects.select_related('user').order_by('-created_at')[:10]
        
        # Recent Users
        context['recent_users'] = User.objects.order_by('-date_joined')[:5]
        
        return context


# ==================== USER MANAGEMENT ====================

class AdminUserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'admin_custom/users/list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.all().prefetch_related('user_roles__role')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset.order_by('-date_joined')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['staff_users'] = User.objects.filter(is_staff=True).count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        from core.models import Role
        context['all_roles'] = Role.objects.filter(is_active=True)
        return context


class AdminUserDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = User
    template_name = 'admin_custom/users/detail.html'
    context_object_name = 'user_obj'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()
        from core.models import UserRole, AuditLog
        context['user_roles'] = UserRole.objects.filter(user=user_obj).select_related('role')
        context['recent_audit'] = AuditLog.objects.filter(
            Q(user=user_obj) |
            Q(table_name='auth_user', record_id=str(user_obj.pk))
        ).order_by('-created_at')[:10]
        # Employee info
        from resources.models import Employee
        try:
            context['employee'] = Employee.objects.select_related('department').get(user=user_obj)
        except Employee.DoesNotExist:
            context['employee'] = None
        return context


class AdminUserCreateView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Tạo user mới + gán role RBAC + audit log."""
    template_name = 'admin_custom/users/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.admin_forms import AdminUserCreateForm
        context['form'] = kwargs.get('form') or AdminUserCreateForm()
        context['form_title'] = 'Tạo Người dùng mới'
        context['is_create'] = True
        return context

    def post(self, request, *args, **kwargs):
        from core.admin_forms import AdminUserCreateForm
        from core.rbac import log_audit, get_client_ip
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user, temp_password = form.save()
            log_audit(
                user=request.user,
                action_type='CREATE',
                table_name='auth_user',
                record_id=user.pk,
                new_data=json.dumps({
                    'username': user.username,
                    'email': user.email,
                    'roles': [r.name for r in form.cleaned_data.get('roles', [])],
                }),
                ip_address=get_client_ip(request),
            )
            messages.success(
                request,
                f'Đã tạo user "{user.username}" thành công. Mật khẩu tạm: {temp_password}'
            )
            return redirect(reverse('admin_custom:users'))
        return self.render_to_response(self.get_context_data(form=form))


class AdminUserEditView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Chỉnh sửa user — đổi role, department, deactivate, reset password."""
    template_name = 'admin_custom/users/form.html'

    def get_user_obj(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.admin_forms import AdminUserEditForm
        user_obj = self.get_user_obj()
        context['form'] = kwargs.get('form') or AdminUserEditForm(user_obj=user_obj)
        context['form_title'] = f'Chỉnh sửa: {user_obj.username}'
        context['user_obj'] = user_obj
        context['is_create'] = False
        return context

    def post(self, request, *args, **kwargs):
        from core.admin_forms import AdminUserEditForm
        from core.rbac import log_audit, get_client_ip
        user_obj = self.get_user_obj()
        form = AdminUserEditForm(request.POST, user_obj=user_obj)
        if form.is_valid():
            user, new_password, changes = form.save()
            if changes:
                log_audit(
                    user=request.user,
                    action_type='UPDATE',
                    table_name='auth_user',
                    record_id=user.pk,
                    old_data=json.dumps({k: v.get('old') if isinstance(v, dict) else v for k, v in changes.items()}),
                    new_data=json.dumps({k: v.get('new') if isinstance(v, dict) else v for k, v in changes.items()}),
                    ip_address=get_client_ip(request),
                )
            msg = f'Đã cập nhật user "{user.username}" thành công.'
            if new_password:
                msg += f' Mật khẩu mới: {new_password}'
            messages.success(request, msg)
            return redirect(reverse('admin_custom:user_detail', kwargs={'pk': user.pk}))
        return self.render_to_response(self.get_context_data(form=form))


class AdminUserDeactivateView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Toggle active/inactive cho user."""
    def post(self, request, *args, **kwargs):
        from core.rbac import log_audit, get_client_ip
        user_obj = get_object_or_404(User, pk=self.kwargs['pk'])
        old_status = user_obj.is_active
        user_obj.is_active = not user_obj.is_active
        user_obj.save()
        action = 'kích hoạt' if user_obj.is_active else 'vô hiệu hóa'
        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='auth_user',
            record_id=user_obj.pk,
            old_data=json.dumps({'is_active': old_status}),
            new_data=json.dumps({'is_active': user_obj.is_active}),
            ip_address=get_client_ip(request),
        )
        messages.success(request, f'Đã {action} tài khoản "{user_obj.username}".')
        return redirect(reverse('admin_custom:users'))


# ==================== AUDIT LOG ====================

class AdminAuditLogView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Xem nhật ký hoạt động hệ thống — ai làm gì, lúc nào."""
    template_name = 'admin_custom/users/audit_log.html'
    context_object_name = 'audit_logs'
    paginate_by = 30

    def get_queryset(self):
        from core.models import AuditLog
        queryset = AuditLog.objects.select_related('user').all()
        action_type = self.request.GET.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        table_name = self.request.GET.get('table_name')
        if table_name:
            queryset = queryset.filter(table_name__icontains=table_name)
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import AuditLog
        context['total_logs'] = AuditLog.objects.count()
        context['action_types'] = AuditLog.ACTION_CHOICES
        context['all_users'] = User.objects.filter(is_active=True).order_by('username')
        return context


# ==================== DEPARTMENT MANAGEMENT ====================

class AdminDepartmentListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Department
    template_name = 'admin_custom/departments/list.html'
    context_object_name = 'departments'
    paginate_by = 20


class AdminDepartmentCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'admin_custom/departments/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã tạo phòng ban "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:departments')


class AdminDepartmentUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'admin_custom/departments/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã cập nhật phòng ban "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:departments')


class AdminDepartmentDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Department
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Đã xóa phòng ban "{self.object.name}".')
        return reverse('admin_custom:departments')


# ==================== ROLE & PERMISSION MANAGEMENT ====================

class AdminRoleListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all RBAC roles with user count and permission count."""
    template_name = 'admin_custom/roles/list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        from core.models import Role
        return Role.objects.filter(is_active=True).annotate(
            user_count=Count('user_roles', distinct=True),
            permission_count=Count('role_permissions', distinct=True),
        ).order_by('name')


class AdminRoleCreateView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Create a new RBAC role."""
    template_name = 'admin_custom/roles/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import Permission
        all_perms = Permission.objects.all().order_by('module', 'code')
        modules = {}
        for p in all_perms:
            modules.setdefault(p.module, []).append({
                'id': p.id, 'code': p.code, 'name': p.name,
            })
        context['modules'] = modules
        return context

    def post(self, request, *args, **kwargs):
        from core.models import Role, RolePermission
        from core.rbac import log_audit
        name = request.POST.get('name', '').strip().upper()
        description = request.POST.get('description', '').strip()
        if not name:
            from django.contrib import messages as msg_framework
            msg_framework.error(request, 'Role name is required.')
            return self.get(request, *args, **kwargs)
        
        role, created = Role.objects.get_or_create(
            name=name,
            defaults={'description': description, 'is_active': True}
        )
        if not created:
            from django.contrib import messages as msg_framework
            msg_framework.warning(request, f'Role {name} already exists.')
            return redirect('admin_custom:role_detail', pk=role.pk)
        
        # Assign selected permissions
        perm_ids = request.POST.getlist('permissions')
        for pid in perm_ids:
            RolePermission.objects.create(role=role, permission_id=int(pid))
        
        log_audit(
            user=request.user,
            action_type='CREATE',
            table_name='roles',
            record_id=str(role.id),
            new_data=f'name={name}, permissions={perm_ids}',
            request=request,
        )
        from django.contrib import messages as msg_framework
        msg_framework.success(request, f'Role {name} created successfully.')
        return redirect('admin_custom:roles')


class AdminRoleDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """View/edit role permissions (permission matrix)."""
    template_name = 'admin_custom/roles/detail.html'
    context_object_name = 'role'

    def get_queryset(self):
        from core.models import Role
        return Role.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import Permission, RolePermission
        role = self.object
        assigned_ids = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        all_perms = Permission.objects.all().order_by('module', 'code')
        # Group by module
        modules = {}
        for p in all_perms:
            modules.setdefault(p.module, []).append({
                'id': p.id,
                'code': p.code,
                'name': p.name,
                'enabled': p.id in assigned_ids,
            })
        context['modules'] = modules
        context['assigned_users'] = User.objects.filter(
            user_roles__role=role
        ).distinct()[:20]
        return context

    def post(self, request, *args, **kwargs):
        """Toggle permissions for this role."""
        from core.models import Permission, RolePermission
        from core.rbac import log_audit
        self.object = self.get_object()
        role = self.object
        selected_ids = set(map(int, request.POST.getlist('permissions')))
        all_perms = Permission.objects.all()

        # Remove unchecked
        RolePermission.objects.filter(role=role).exclude(
            permission_id__in=selected_ids
        ).delete()

        # Add new
        existing = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        for pid in selected_ids - existing:
            RolePermission.objects.create(role=role, permission_id=pid)

        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='role_permissions',
            record_id=str(role.id),
            new_data=f'permissions={list(selected_ids)}',
            request=request,
        )
        from django.contrib import messages as msg_framework
        msg_framework.success(request, f'Permissions for role {role.name} updated.')
        return redirect('admin_custom:role_detail', pk=role.pk)


# ==================== PROJECT ACCESS CONTROL ====================

class AdminProjectAccessView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """User-Project-Role assignment matrix.
    Admin chỉ thấy User + Project ID + Role, KHÔNG thấy budget/profit/finance."""
    template_name = 'admin_custom/project_access/list.html'
    context_object_name = 'assignments'
    paginate_by = 30

    def get_queryset(self):
        from projects.models import Task
        # Show project members via tasks (assigned_to)
        qs = Task.objects.select_related(
            'project', 'assigned_to__user'
        ).exclude(assigned_to__isnull=True).values(
            'assigned_to__user__id',
            'assigned_to__user__username',
            'assigned_to__user__first_name',
            'assigned_to__user__last_name',
            'project__id',
            'project__name',
        ).distinct().order_by('project__name')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from projects.models import Project
        context['projects'] = Project.objects.all().order_by('name')
        return context


# ==================== SYSTEM SETTINGS ====================

class AdminSystemSettingsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """System configuration page."""
    template_name = 'admin_custom/settings/system.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['debug_mode'] = settings.DEBUG
        context['database_engine'] = settings.DATABASES.get('default', {}).get('ENGINE', '')
        context['database_name'] = settings.DATABASES.get('default', {}).get('NAME', '')
        context['timezone'] = settings.TIME_ZONE
        context['language'] = settings.LANGUAGE_CODE
        context['installed_apps'] = settings.INSTALLED_APPS
        return context