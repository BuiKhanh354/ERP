"""
Views quản lý Phòng ban dành cho Admin.
Sử dụng PermissionRequiredMixin từ core.rbac – superuser tự động bypass.
"""
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView, View
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q, Count
from django.contrib import messages
from django.shortcuts import redirect

from core.rbac import PermissionRequiredMixin, log_audit, get_client_ip
from core.admin_department_forms import AdminDepartmentForm
from resources.models import Department, Employee


class AdminDepartmentListView(PermissionRequiredMixin, ListView):
    """Danh sách phòng ban với tìm kiếm, lọc, sắp xếp."""
    model = Department
    template_name = 'modules/admin/pages/departments_list.html'
    context_object_name = 'departments'
    paginate_by = 20

    def get_queryset(self):
        qs = Department.objects.select_related('parent', 'manager').annotate(
            num_employees=Count('employee', filter=Q(employee__is_active=True))
        )

        # Tìm kiếm
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )

        # Lọc theo trạng thái
        status = self.request.GET.get('status', '')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        # Sắp xếp
        sort = self.request.GET.get('sort', 'name')
        direction = self.request.GET.get('dir', 'asc')
        valid_sorts = {
            'name': 'name',
            'code': 'code',
            'created_at': 'created_at',
            'employees': 'num_employees',
        }
        sort_field = valid_sorts.get(sort, 'name')
        if direction == 'desc':
            sort_field = f'-{sort_field}'
        qs = qs.order_by(sort_field)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'name')
        ctx['current_dir'] = self.request.GET.get('dir', 'asc')
        ctx['total_departments'] = Department.objects.count()
        ctx['active_departments'] = Department.objects.filter(is_active=True).count()
        ctx['inactive_departments'] = Department.objects.filter(is_active=False).count()
        return ctx


class AdminDepartmentCreateView(PermissionRequiredMixin, CreateView):
    """Tạo phòng ban mới."""
    model = Department
    form_class = AdminDepartmentForm
    template_name = 'modules/admin/pages/department_form.html'
    success_url = reverse_lazy('admin_module:department_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Tạo phòng ban mới'
        ctx['submit_label'] = 'Tạo phòng ban'
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_audit(
            user=self.request.user,
            action_type='CREATE',
            table_name='resources_department',
            record_id=self.object.pk,
            new_data={'name': self.object.name, 'code': self.object.code},
            ip_address=get_client_ip(self.request),
        )
        messages.success(self.request, f'Đã tạo phòng ban "{self.object.name}" thành công.')
        return response


class AdminDepartmentUpdateView(PermissionRequiredMixin, UpdateView):
    """Chỉnh sửa phòng ban."""
    model = Department
    form_class = AdminDepartmentForm
    template_name = 'modules/admin/pages/department_form.html'
    success_url = reverse_lazy('admin_module:department_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = f'Chỉnh sửa: {self.object.name}'
        ctx['submit_label'] = 'Lưu thay đổi'
        return ctx

    def form_valid(self, form):
        old_data = {
            'name': Department.objects.get(pk=self.object.pk).name,
            'code': Department.objects.get(pk=self.object.pk).code,
        }
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        log_audit(
            user=self.request.user,
            action_type='UPDATE',
            table_name='resources_department',
            record_id=self.object.pk,
            old_data=old_data,
            new_data={'name': self.object.name, 'code': self.object.code},
            ip_address=get_client_ip(self.request),
        )
        messages.success(self.request, f'Đã cập nhật phòng ban "{self.object.name}" thành công.')
        return response


class AdminDepartmentDetailView(PermissionRequiredMixin, DetailView):
    """Chi tiết phòng ban: thông tin, phòng ban con, danh sách nhân viên."""
    model = Department
    template_name = 'modules/admin/pages/department_detail.html'
    context_object_name = 'department'

    def get_queryset(self):
        return Department.objects.select_related('parent', 'manager')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = self.object
        ctx['sub_departments'] = dept.children.all().annotate(
            num_employees=Count('employee', filter=Q(employee__is_active=True))
        )
        ctx['employees'] = Employee.objects.filter(
            department=dept, is_active=True
        ).select_related('department')
        ctx['ancestors'] = dept.get_ancestors()
        # Available employees (not in this department)
        ctx['available_employees'] = Employee.objects.exclude(
            department=dept
        ).filter(is_active=True).select_related('department', 'position_fk')[:50]
        return ctx


class AdminDepartmentToggleStatusView(PermissionRequiredMixin, View):
    """Kích hoạt / Vô hiệu hóa phòng ban (POST)."""

    def post(self, request, pk):
        try:
            dept = Department.objects.get(pk=pk)
        except Department.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Phòng ban không tồn tại.'}, status=404)

        old_status = dept.is_active
        dept.is_active = not dept.is_active
        dept.updated_by = request.user
        dept.save(update_fields=['is_active', 'updated_by', 'updated_at'])

        action = 'kích hoạt' if dept.is_active else 'vô hiệu hóa'
        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='resources_department',
            record_id=dept.pk,
            old_data={'is_active': old_status},
            new_data={'is_active': dept.is_active},
            ip_address=get_client_ip(request),
        )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'is_active': dept.is_active,
                'message': f'Đã {action} phòng ban "{dept.name}".',
            })

        messages.success(request, f'Đã {action} phòng ban "{dept.name}".')
        from django.shortcuts import redirect
        return redirect('admin_module:department_list')


class AdminDepartmentHierarchyView(PermissionRequiredMixin, TemplateView):
    """Hiển thị sơ đồ tổ chức dạng cây."""
    template_name = 'modules/admin/pages/department_hierarchy.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Lấy tất cả phòng ban gốc (không có parent)
        root_departments = Department.objects.filter(
            parent__isnull=True
        ).prefetch_related('children').order_by('name')
        ctx['root_departments'] = root_departments
        ctx['total_departments'] = Department.objects.count()
        ctx['active_departments'] = Department.objects.filter(is_active=True).count()
        return ctx


class DepartmentEmployeeListView(PermissionRequiredMixin, View):
    """Danh sách nhân viên theo phòng ban (AJAX)."""

    def get(self, request, pk):
        try:
            dept = Department.objects.get(pk=pk)
        except Department.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Phòng ban không tồn tại.'}, status=404)

        employees = Employee.objects.filter(department=dept).select_related('user', 'position_fk')

        data = []
        for emp in employees:
            data.append({
                'id': emp.pk,
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'email': emp.email,
                'position': emp.position or '—',
                'employment_type': emp.get_employment_type_display(),
                'is_active': emp.is_active,
            })

        return JsonResponse({'ok': True, 'employees': data})


class AddEmployeeToDepartmentView(PermissionRequiredMixin, View):
    """Thêm nhân viên vào phòng ban (POST)."""

    def post(self, request, pk):
        try:
            dept = Department.objects.get(pk=pk)
        except Department.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Phòng ban không tồn tại.'}, status=404)

        # Lấy danh sách employee IDs từ request
        import json
        try:
            data = json.loads(request.body)
            employee_ids = data.get('employee_ids', [])
        except (json.JSONDecodeError, AttributeError):
            employee_ids = request.POST.getlist('employee_ids')

        if not employee_ids:
            return JsonResponse({'ok': False, 'message': 'Chưa chọn nhân viên nào.'}, status=400)

        # Cập nhật department cho các employee
        updated_count = 0
        for emp_id in employee_ids:
            try:
                emp = Employee.objects.get(pk=emp_id)
                old_dept = emp.department.name if emp.department else None
                emp.department = dept
                emp.save(update_fields=['department', 'updated_at'])

                log_audit(
                    user=request.user,
                    action_type='UPDATE',
                    table_name='resources_employee',
                    record_id=emp.pk,
                    old_data={'department': old_dept},
                    new_data={'department': dept.name},
                    ip_address=get_client_ip(request),
                )
                updated_count += 1
            except Employee.DoesNotExist:
                continue

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': f'Đã thêm {updated_count} nhân viên vào phòng ban "{dept.name}".',
                'updated_count': updated_count,
            })

        messages.success(request, f'Đã thêm {updated_count} nhân viên vào phòng ban "{dept.name}".')
        return redirect('admin_module:department_detail', pk=pk)


class RemoveEmployeeFromDepartmentView(PermissionRequiredMixin, View):
    """Xóa nhân viên khỏi phòng ban (POST)."""

    def post(self, request, pk, employee_id):
        try:
            dept = Department.objects.get(pk=pk)
        except Department.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Phòng ban không tồn tại.'}, status=404)

        try:
            emp = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Nhân viên không tồn tại.'}, status=404)

        if emp.department != dept:
            return JsonResponse({'ok': False, 'message': 'Nhân viên không thuộc phòng ban này.'}, status=400)

        old_dept = emp.department.name
        emp.department = None
        emp.save(update_fields=['department', 'updated_at'])

        log_audit(
            user=request.user,
            action_type='UPDATE',
            table_name='resources_employee',
            record_id=emp.pk,
            old_data={'department': old_dept},
            new_data={'department': None},
            ip_address=get_client_ip(request),
        )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': f'Đã xóa nhân viên "{emp.full_name}" khỏi phòng ban "{dept.name}".',
            })

        messages.success(request, f'Đã xóa nhân viên "{emp.full_name}" khỏi phòng ban "{dept.name}".')
        return redirect('admin_module:department_detail', pk=pk)
