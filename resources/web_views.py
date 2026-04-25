"""Web views for Resource Management."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View

from .models import Employee, Department, ResourceAllocation, Position, PayrollSchedule, EmployeeHourlyRate
from core.notification_service import NotificationService
from core.models import Notification
from .forms import EmployeeForm, DepartmentForm
from .payroll_forms import PayrollScheduleForm
from projects.models import Project
from core.mixins import ManagerRequiredMixin
from .performance_services import EmployeePerformanceService


class EmployeeListView(LoginRequiredMixin, ListView):
    """Danh sách nhân sự."""
    model = Employee
    template_name = 'resources/list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        # Quản lý xem tất cả, nhân viên chỉ xem của mình
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            queryset = Employee.objects.all().select_related('department').annotate(
                project_count=Count('allocations__project', distinct=True)
            )
        else:
            queryset = Employee.objects.filter(created_by=user).select_related('department').annotate(
                project_count=Count('allocations__project', distinct=True, filter=Q(allocations__project__created_by=user))
            )
        queryset = queryset.order_by('-created_at')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(position__icontains=search)
            )

        department_filter = self.request.GET.get('department')
        if department_filter:
            queryset = queryset.filter(department_id=department_filter)

        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.all()
        context['search_query'] = self.request.GET.get('search', '')
        context['department_filter'] = self.request.GET.get('department', '')
        context['status_filter'] = self.request.GET.get('status', '')
        
        # Stats - quản lý xem tất cả, nhân viên chỉ của mình
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            user_employees = Employee.objects.all()
        else:
            user_employees = Employee.objects.filter(created_by=user)
        context['total_employees'] = user_employees.count()
        context['active_employees'] = user_employees.filter(is_active=True).count()
        context['departments_count'] = Department.objects.count()  # Departments có thể shared
        
        return context


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    """Chi tiết nhân sự."""
    model = Employee
    template_name = 'resources/detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        """Quản lý xem tất cả, nhân viên chỉ xem của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Employee.objects.all()
        return Employee.objects.filter(created_by=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.get_object()
        
        # Filter allocations và scores theo user
        context['allocations'] = employee.allocations.filter(
            project__created_by=self.request.user
        ).select_related('project').order_by('-start_date')
        # Manager xem tất cả đánh giá, nhân viên chỉ xem của mình
        context['scores'] = []
        
        # L???ch s??? l????ng/gi???
        context['hourly_rate_history'] = []
        # Điểm hiệu suất trung bình theo yêu cầu mới:
        # dựa trên mức chi tiêu dự án + mức độ hoàn thành công việc
        perf = EmployeePerformanceService.calculate(employee)
        context['avg_performance'] = perf["overall"]
        context["performance_breakdown"] = perf
        
        return context


class EmployeeCreateView(ManagerRequiredMixin, CreateView):
    """Tạo nhân sự mới - chỉ quản lý mới có quyền."""
    model = Employee
    form_class = EmployeeForm
    template_name = 'resources/form.html'
    success_url = reverse_lazy('resources:list')

    def form_valid(self, form):
        from django.contrib.auth import get_user_model
        from core.models import UserProfile
        
        User = get_user_model()
        form.instance.created_by = self.request.user
        
        # Tạo User với mật khẩu mặc định
        email = form.cleaned_data['email']
        role = form.cleaned_data.get('role', 'employee')
        
        # Kiểm tra xem email đã tồn tại chưa
        if User.objects.filter(email__iexact=email).exists():
            form.add_error('email', 'Email này đã được sử dụng. Vui lòng chọn email khác.')
            return self.form_invalid(form)
        
        # Tạo username từ email (lấy phần trước @)
        username = email.split('@')[0]
        # Đảm bảo username là unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Tạo User
        user = User.objects.create_user(
            username=username,
            email=email,
            password='12345678',  # Mật khẩu mặc định
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
        )
        
        # Tạo UserProfile với role
        UserProfile.objects.create(
            user=user,
            role=role
        )
        
        # Liên kết Employee với User
        form.instance.user = user
        
        # Đánh dấu user cần đổi mật khẩu lần đầu
        # Sử dụng một flag trong session hoặc một field trong UserProfile
        # Ở đây ta sẽ kiểm tra bằng cách so sánh password hash với mật khẩu mặc định
        
        messages.success(self.request, f'Đã tạo nhân sự "{form.instance.full_name}" thành công. Tài khoản đã được tạo với mật khẩu mặc định: 12345678')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Tạo nhân sự mới'
        context['submit_text'] = 'Tạo nhân sự'
        context['positions'] = Position.objects.filter(is_active=True).order_by('name')
        return context


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    """Cập nhật nhân sự."""
    model = Employee
    form_class = EmployeeForm
    template_name = 'resources/form.html'
    success_url = reverse_lazy('resources:list')

    def get_queryset(self):
        """Quản lý có thể sửa tất cả, nhân viên chỉ sửa của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Employee.objects.all()
        return Employee.objects.filter(created_by=user)

    def form_valid(self, form):
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()

        # Detect thay đổi lương/giờ trước khi save
        old_employee = self.get_object()
        old_rate = old_employee.hourly_rate

        form.instance.updated_by = user
        response = super().form_valid(form)

        # Nếu quản lý đổi lương -> thông báo cho nhân viên đó
        try:
            new_employee = self.object
            new_rate = new_employee.hourly_rate
            if is_manager and new_rate is not None and old_rate != new_rate and getattr(new_employee, "user", None):
                NotificationService.notify(
                    user=new_employee.user,
                    title="Lương/giờ của bạn đã được cập nhật",
                    message=f"Mức lương/giờ của bạn đã được cập nhật: {old_rate} → {new_rate} VNĐ/giờ.",
                    level=Notification.LEVEL_INFO,
                    url="/resources/salary-tracking/" if True else "",
                    actor=user,
                )
        except Exception:
            pass

        messages.success(self.request, f'Đã cập nhật nhân sự "{form.instance.full_name}" thành công.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Chỉnh sửa: {self.get_object().full_name}'
        context['submit_text'] = 'Cập nhật'
        context['positions'] = Position.objects.filter(is_active=True).order_by('name')
        return context


class EmployeeDeleteView(ManagerRequiredMixin, DeleteView):
    """Xóa nhân sự - chỉ quản lý mới có quyền."""
    model = Employee
    template_name = 'resources/confirm_delete.html'
    success_url = reverse_lazy('resources:list')

    def get_queryset(self):
        """Quản lý có thể xóa tất cả."""
        return Employee.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.get_object()
        
        # Kiểm tra xem nhân sự có đang làm việc không
        from projects.models import Task, TimeEntry
        from resources.models import ResourceAllocation
        from django.utils import timezone
        from datetime import timedelta
        
        # Kiểm tra tasks đang active
        active_tasks = Task.objects.filter(
            assigned_to=employee,
            status__in=['todo', 'in_progress', 'review']
        ).count()
        
        # Kiểm tra allocations đang active
        today = timezone.now().date()
        active_allocations = ResourceAllocation.objects.filter(
            employee=employee,
            start_date__lte=today
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).count()
        
        # Kiểm tra time entries trong 30 ngày gần nhất
        recent_time_entries = TimeEntry.objects.filter(
            employee=employee,
            date__gte=today - timedelta(days=30)
        ).count()
        
        context['has_active_work'] = active_tasks > 0 or active_allocations > 0 or recent_time_entries > 0
        context['active_tasks'] = active_tasks
        context['active_allocations'] = active_allocations
        context['recent_time_entries'] = recent_time_entries
        
        return context

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        
        # Kiểm tra lại trước khi xóa
        from projects.models import Task, TimeEntry
        from resources.models import ResourceAllocation
        from django.utils import timezone
        from datetime import timedelta
        
        active_tasks = Task.objects.filter(
            assigned_to=employee,
            status__in=['todo', 'in_progress', 'review']
        ).count()
        
        today = timezone.now().date()
        active_allocations = ResourceAllocation.objects.filter(
            employee=employee,
            start_date__lte=today
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).count()
        
        if active_tasks > 0 or active_allocations > 0:
            messages.error(
                request,
                f'Không thể xóa nhân sự "{employee.full_name}" vì đang có công việc hoặc phân bổ dự án đang hoạt động. '
                f'Vui lòng hoàn tất hoặc hủy các công việc/dự án trước khi xóa.'
            )
            return redirect('resources:detail', pk=employee.pk)
        
        employee_name = employee.full_name
        messages.success(request, f'Đã xóa nhân sự "{employee_name}".')
        result = super().delete(request, *args, **kwargs)
        
        # Redirect với parameter để hiển thị modal thông báo thành công
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from urllib.parse import quote
        return HttpResponseRedirect(reverse('resources:list') + f'?deleted={quote(employee_name)}')


class DepartmentListView(LoginRequiredMixin, ListView):
    """Danh sách phòng ban."""
    model = Department
    template_name = 'resources/department_list.html'
    context_object_name = 'departments'
    
    def get_queryset(self):
        queryset = Department.objects.all().select_related('manager').annotate(
            employee_count=models.Count('employee', distinct=True)
        ).order_by('name')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['total_departments'] = Department.objects.count()
        return context


class DepartmentCreateView(ManagerRequiredMixin, CreateView):
    """Tạo phòng ban mới - chỉ quản lý mới có quyền."""
    model = Department
    form_class = DepartmentForm
    template_name = 'resources/department_form.html'
    success_url = reverse_lazy('resources:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Đã tạo phòng ban "{form.instance.name}" thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Tạo phòng ban mới'
        context['submit_text'] = 'Tạo phòng ban'
        context['employees'] = Employee.objects.filter(is_active=True).order_by('last_name', 'first_name')
        return context


class DepartmentUpdateView(ManagerRequiredMixin, UpdateView):
    """Cập nhật phòng ban."""
    model = Department
    form_class = DepartmentForm
    template_name = 'resources/department_form.html'
    success_url = reverse_lazy('resources:list')

    def get_queryset(self):
        """Quản lý có thể sửa tất cả."""
        return Department.objects.all()

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Đã cập nhật phòng ban "{form.instance.name}" thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Chỉnh sửa: {self.get_object().name}'
        context['submit_text'] = 'Cập nhật'
        context['employees'] = Employee.objects.filter(is_active=True).order_by('last_name', 'first_name')
        return context


class DepartmentDeleteView(ManagerRequiredMixin, DeleteView):
    """Xóa phòng ban - chỉ quản lý mới có quyền."""
    model = Department
    template_name = 'resources/department_confirm_delete.html'
    success_url = reverse_lazy('resources:list')

    def get_queryset(self):
        """Quản lý có thể xóa tất cả."""
        return Department.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.get_object()
        
        # Kiểm tra xem phòng ban có nhân viên không
        employee_count = Employee.objects.filter(department=department).count()
        context['employee_count'] = employee_count
        context['has_employees'] = employee_count > 0
        
        return context

    def delete(self, request, *args, **kwargs):
        department = self.get_object()
        
        # Kiểm tra lại trước khi xóa
        employee_count = Employee.objects.filter(department=department).count()
        if employee_count > 0:
            messages.error(
                request,
                f'Không thể xóa phòng ban "{department.name}" vì đang có {employee_count} nhân viên. '
                f'Vui lòng chuyển nhân viên sang phòng ban khác trước khi xóa.'
            )
            return redirect('resources:list')
        
        department_name = department.name
        messages.success(request, f'Đã xóa phòng ban "{department_name}".')
        return super().delete(request, *args, **kwargs)


class PayrollScheduleView(ManagerRequiredMixin, View):
    """View để cài đặt lịch phát lương chung cho toàn bộ nhân viên."""
    
    def get(self, request):
        # Lấy hoặc tạo payroll schedule chung (chỉ có 1 record)
        payroll_schedule = PayrollSchedule.get_active_schedule()
        if not payroll_schedule:
            # Nếu chưa có, tạo mới
            payroll_schedule = PayrollSchedule.objects.create(
                payment_day=5,
                is_active=True,
                created_by=request.user
            )
        
        form = PayrollScheduleForm(instance=payroll_schedule)
        
        from django.template.response import TemplateResponse
        
        return TemplateResponse(
            request,
            'resources/payroll_schedule_form.html',
            {
                'form': form,
                'payroll_schedule': payroll_schedule,
                'page_title': 'Cài đặt lịch phát lương'
            }
        )
    
    def post(self, request):
        # Lấy hoặc tạo payroll schedule chung
        payroll_schedule = PayrollSchedule.get_active_schedule()
        if not payroll_schedule:
            payroll_schedule = PayrollSchedule.objects.create(
                payment_day=5,
                is_active=True,
                created_by=request.user
            )
        
        form = PayrollScheduleForm(request.POST, instance=payroll_schedule)
        
        if form.is_valid():
            form.instance.is_active = True
            form.instance.created_by = request.user
            form.save()
            messages.success(
                request,
                f'Đã cài đặt lịch phát lương chung. '
                f'Lương sẽ được phát vào ngày {form.instance.payment_day} hàng tháng cho tất cả nhân viên.'
            )
            return redirect('core:dashboard')
        
        from django.template.response import TemplateResponse
        
        return TemplateResponse(
            request,
            'resources/payroll_schedule_form.html',
            {
                'form': form,
                'payroll_schedule': payroll_schedule,
                'page_title': 'Cài đặt lịch phát lương'
            }
        )


class CreatePositionView(LoginRequiredMixin, View):
    """API endpoint để tạo chức vụ mới (AJAX)."""
    def post(self, request):
        from django.http import JsonResponse
        import json
        
        if not hasattr(request.user, 'profile') or not request.user.profile.is_manager():
            return JsonResponse({'success': False, 'error': 'Chỉ quản lý mới có quyền tạo chức vụ.'})
        
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Tên chức vụ không được để trống.'})
        
        # Kiểm tra xem chức vụ đã tồn tại chưa
        if Position.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'error': f'Chức vụ "{name}" đã tồn tại.'})
        
        try:
            position = Position.objects.create(
                name=name,
                description=data.get('description', '').strip(),
                created_by=request.user
            )
            return JsonResponse({
                'success': True,
                'position': {
                    'id': position.id,
                    'name': position.name
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Lỗi khi tạo chức vụ: {str(e)}'})

