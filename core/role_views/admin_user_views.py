"""
Admin User Management views.
CRUD, toggle status, reset password, assign role/department.
Uses PermissionRequiredMixin — superuser auto-bypass.
"""
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q, Prefetch
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect

from core.rbac import PermissionRequiredMixin, log_audit, get_client_ip
from core.models import Role, UserRole, AuditLog
from resources.models import Department, Employee


class AdminUserListView(PermissionRequiredMixin, ListView):
    """Danh sách người dùng với tìm kiếm, lọc vai trò, lọc trạng thái."""
    model = User
    template_name = 'modules/admin/pages/users_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.select_related('profile').prefetch_related(
            Prefetch('user_roles', queryset=UserRole.objects.select_related('role'))
        ).order_by('-date_joined')

        # Search
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )

        # Filter by status
        status = self.request.GET.get('status', '')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        # Filter by role
        role_id = self.request.GET.get('role', '')
        if role_id:
            qs = qs.filter(user_roles__role_id=role_id)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_role'] = self.request.GET.get('role', '')
        ctx['roles'] = Role.objects.filter(is_active=True)
        ctx['total_users'] = User.objects.count()
        ctx['active_users'] = User.objects.filter(is_active=True).count()
        ctx['inactive_users'] = User.objects.filter(is_active=False).count()
        return ctx


class AdminUserCreateView(PermissionRequiredMixin, CreateView):
    """Tạo người dùng mới."""
    model = User
    template_name = 'modules/admin/pages/user_form.html'
    fields = ['username', 'email', 'first_name', 'last_name']
    success_url = reverse_lazy('admin_module:user_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Thêm người dùng mới'
        ctx['submit_label'] = 'Tạo người dùng'
        ctx['roles'] = Role.objects.filter(is_active=True)
        ctx['departments'] = Department.objects.filter(is_active=True)
        return ctx

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in form.fields:
            form.fields[field_name].widget.attrs['class'] = 'form-control'
        form.fields['username'].widget.attrs['placeholder'] = 'Tên đăng nhập'
        form.fields['email'].widget.attrs['placeholder'] = 'Email'
        form.fields['first_name'].widget.attrs['placeholder'] = 'Họ'
        form.fields['last_name'].widget.attrs['placeholder'] = 'Tên'
        return form

    def form_valid(self, form):
        user = form.save(commit=False)
        # Set default password
        default_pw = '12345678'
        user.set_password(default_pw)
        user.is_active = True
        user.save()

        # Create UserProfile
        from core.models import UserProfile
        UserProfile.objects.get_or_create(user=user)

        # Assign role
        role_id = self.request.POST.get('role_id')
        if role_id:
            try:
                role = Role.objects.get(pk=role_id)
                UserRole.objects.get_or_create(user=user, role=role)
            except Role.DoesNotExist:
                pass

        # Assign department via Employee
        dept_id = self.request.POST.get('department_id')
        if dept_id:
            try:
                dept = Department.objects.get(pk=dept_id)
                Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        'full_name': user.get_full_name() or user.username,
                        'email': user.email,
                        'department': dept,
                        'employee_id': f'EMP{user.pk:04d}',
                    }
                )
            except Department.DoesNotExist:
                pass

        log_audit(
            user=self.request.user,
            action_type='CREATE',
            table_name='auth_user',
            record_id=user.pk,
            new_data={'username': user.username, 'email': user.email},
            ip_address=get_client_ip(self.request),
        )
        messages.success(self.request, f'Đã tạo người dùng "{user.username}" với mật khẩu mặc định: {default_pw}')
        return redirect(self.success_url)


class AdminUserEditView(PermissionRequiredMixin, UpdateView):
    """Chỉnh sửa thông tin người dùng."""
    model = User
    template_name = 'modules/admin/pages/user_form.html'
    fields = ['username', 'email', 'first_name', 'last_name']
    success_url = reverse_lazy('admin_module:user_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Chỉnh sửa: {self.object.username}'
        ctx['submit_label'] = 'Lưu thay đổi'
        ctx['roles'] = Role.objects.filter(is_active=True)
        ctx['departments'] = Department.objects.filter(is_active=True)
        ctx['user_obj'] = self.object
        # Current role
        ur = UserRole.objects.filter(user=self.object).select_related('role').first()
        ctx['current_role_id'] = ur.role.pk if ur else ''
        # Current department
        emp = Employee.objects.filter(user=self.object).first()
        ctx['current_department_id'] = emp.department_id if emp and emp.department_id else ''
        return ctx

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in form.fields:
            form.fields[field_name].widget.attrs['class'] = 'form-control'
        return form

    def form_valid(self, form):
        user = form.save()

        # Update role
        role_id = self.request.POST.get('role_id')
        if role_id:
            UserRole.objects.filter(user=user).delete()
            try:
                role = Role.objects.get(pk=role_id)
                UserRole.objects.get_or_create(user=user, role=role)
            except Role.DoesNotExist:
                pass

        # Update department
        dept_id = self.request.POST.get('department_id')
        if dept_id:
            try:
                dept = Department.objects.get(pk=dept_id)
                emp, _ = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        'full_name': user.get_full_name() or user.username,
                        'email': user.email,
                        'employee_id': f'EMP{user.pk:04d}',
                    }
                )
                emp.department = dept
                emp.save(update_fields=['department'])
            except Department.DoesNotExist:
                pass

        log_audit(
            user=self.request.user,
            action_type='UPDATE',
            table_name='auth_user',
            record_id=user.pk,
            new_data={'username': user.username, 'email': user.email},
            ip_address=get_client_ip(self.request),
        )
        messages.success(self.request, f'Đã cập nhật người dùng "{user.username}".')
        return redirect(self.success_url)


class AdminUserToggleStatusView(PermissionRequiredMixin, View):
    """Kích hoạt / Vô hiệu hóa người dùng."""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Không cho vô hiệu hóa chính mình
        if user == request.user:
            messages.error(request, 'Không thể vô hiệu hóa tài khoản của chính bạn.')
            return redirect('admin_module:user_list')

        old_status = user.is_active
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        action = 'kích hoạt' if user.is_active else 'vô hiệu hóa'
        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='auth_user',
            record_id=user.pk,
            old_data={'is_active': old_status},
            new_data={'is_active': user.is_active},
            ip_address=get_client_ip(request),
        )
        messages.success(request, f'Đã {action} tài khoản "{user.username}".')
        return redirect('admin_module:user_list')


class AdminUserResetPasswordView(PermissionRequiredMixin, View):
    """Reset mật khẩu về mặc định."""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        default_pw = '12345678'
        user.set_password(default_pw)
        user.save()

        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='auth_user',
            record_id=user.pk,
            new_data={'action': 'password_reset'},
            ip_address=get_client_ip(request),
        )
        messages.success(request, f'Đã đặt lại mật khẩu cho "{user.username}" thành: {default_pw}')
        return redirect('admin_module:user_list')


class AdminAuditLogListView(PermissionRequiredMixin, ListView):
    """Nhật ký hệ thống (Audit Logs)."""
    model = AuditLog
    template_name = 'modules/admin/pages/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user').order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(table_name__icontains=q) |
                Q(user__username__icontains=q) |
                Q(action_type__icontains=q)
            )

        action = self.request.GET.get('action', '')
        if action:
            qs = qs.filter(action_type=action)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_action'] = self.request.GET.get('action', '')
        ctx['total_logs'] = AuditLog.objects.count()
        return ctx
