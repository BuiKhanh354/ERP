"""
Custom Admin Views với UI giống Client Site - Đầy đủ CRUD operations.
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
import csv
import json

from core.models import UserProfile, Notification, AIChatHistory
from projects.models import Project, Task, TimeEntry
from budgeting.models import BudgetCategory, Budget, Expense
from resources.models import Department, Employee, ResourceAllocation
from clients.models import Client, Contact, ClientInteraction
from performance.models import PerformanceScore, PerformanceMetric
from ai.models import AIInsight

# Import forms
from projects.forms import ProjectForm, TaskForm
from clients.forms import ClientForm, ContactForm, ClientInteractionForm
from resources.forms import DepartmentForm, EmployeeForm, ResourceAllocationForm
from budgeting.forms import BudgetForm, ExpenseForm


def is_staff_user(user):
    """Kiểm tra user có phải staff không."""
    return user.is_authenticated and user.is_staff


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin yêu cầu user phải là staff."""
    def test_func(self):
        return is_staff_user(self.request.user)


class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Trang dashboard admin với quick actions thực sự hoạt động."""
    template_name = 'admin_custom/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Thống kê tổng quan
        context['total_users'] = User.objects.count()
        context['total_projects'] = Project.objects.count()
        context['active_projects'] = Project.objects.filter(status='active').count()
        context['total_employees'] = Employee.objects.count()
        context['total_clients'] = Client.objects.count()
        context['total_budgets'] = Budget.objects.count()
        context['total_expenses'] = Expense.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        context['total_tasks'] = Task.objects.count()
        context['pending_tasks'] = Task.objects.filter(status='todo').count()
        
        # Thống kê gần đây
        context['recent_projects'] = Project.objects.select_related('client').order_by('-created_at')[:5]
        context['recent_users'] = User.objects.order_by('-date_joined')[:5]
        context['recent_tasks'] = Task.objects.select_related('project', 'assigned_to').order_by('-created_at')[:5]
        context['recent_employees'] = Employee.objects.select_related('department').order_by('-created_at')[:5]
        
        # Thống kê theo trạng thái
        context['project_status_stats'] = Project.objects.values('status').annotate(count=Count('id'))
        context['task_status_stats'] = Task.objects.values('status').annotate(count=Count('id'))
        
        return context


# ==================== USER MANAGEMENT ====================

class AdminUserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'admin_custom/users/list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.all().select_related('userprofile')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        return queryset.order_by('-date_joined')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['staff_users'] = User.objects.filter(is_staff=True).count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        return context


class AdminUserDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = User
    template_name = 'admin_custom/users/detail.html'
    context_object_name = 'user_obj'


# ==================== PROJECT MANAGEMENT ====================

class AdminProjectListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Project
    template_name = 'admin_custom/projects/list.html'
    context_object_name = 'projects'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Project.objects.select_related('client').all()
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(client__name__icontains=search)
            )
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Project.STATUS_CHOICES
        context['total_projects'] = Project.objects.count()
        context['active_projects'] = Project.objects.filter(status='active').count()
        return context


class AdminProjectCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'admin_custom/projects/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã tạo dự án "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:projects').url


class AdminProjectUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'admin_custom/projects/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã cập nhật dự án "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:projects').url


class AdminProjectDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Project
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Đã xóa dự án "{self.object.name}".')
        return reverse('admin_custom:projects')


# ==================== TASK MANAGEMENT ====================

class AdminTaskListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Task
    template_name = 'admin_custom/tasks/list.html'
    context_object_name = 'tasks'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Task.objects.select_related('project', 'assigned_to').all()
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        project_id = self.request.GET.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Task.STATUS_CHOICES
        context['projects'] = Project.objects.all()
        return context


class AdminTaskCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'admin_custom/tasks/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã tạo công việc "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:tasks')


class AdminTaskUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'admin_custom/tasks/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã cập nhật công việc "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:tasks')


class AdminTaskDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Task
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Đã xóa công việc "{self.object.name}".')
        return reverse('admin_custom:tasks')


# ==================== EMPLOYEE MANAGEMENT ====================

class AdminEmployeeListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Employee
    template_name = 'admin_custom/employees/list.html'
    context_object_name = 'employees'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Employee.objects.select_related('department', 'user').all()
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search)
            )
        return queryset.order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.all()
        return context


class AdminEmployeeCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'admin_custom/employees/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã tạo nhân sự "{form.instance.full_name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:employees')


class AdminEmployeeUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'admin_custom/employees/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã cập nhật nhân sự "{form.instance.full_name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:employees')


class AdminEmployeeDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Employee
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Đã xóa nhân sự "{self.object.full_name}".')
        return reverse('admin_custom:employees')


# ==================== CLIENT MANAGEMENT ====================

class AdminClientListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Client
    template_name = 'admin_custom/clients/list.html'
    context_object_name = 'clients'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Client.objects.all()
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Client.STATUS_CHOICES
        return context


class AdminClientCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'admin_custom/clients/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã tạo khách hàng "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:clients')


class AdminClientUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'admin_custom/clients/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'Đã cập nhật khách hàng "{form.instance.name}" thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:clients')


class AdminClientDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Client
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Đã xóa khách hàng "{self.object.name}".')
        return reverse('admin_custom:clients')


# ==================== BUDGET MANAGEMENT ====================

class AdminBudgetListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Budget
    template_name = 'admin_custom/budgets/list.html'
    context_object_name = 'budgets'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Budget.objects.select_related('project', 'category').all()
        project_id = self.request.GET.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset.order_by('-fiscal_year', 'category')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all()
        context['categories'] = BudgetCategory.objects.all()
        return context


class AdminBudgetCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'admin_custom/budgets/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'Đã tạo ngân sách thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:budgets')


class AdminBudgetUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'admin_custom/budgets/form.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'Đã cập nhật ngân sách thành công.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('admin_custom:budgets')


class AdminBudgetDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Budget
    template_name = 'admin_custom/confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, 'Đã xóa ngân sách.')
        return reverse('admin_custom:budgets')


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


# ==================== PERFORMANCE MANAGEMENT ====================

class AdminPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = PerformanceScore
    template_name = 'admin_custom/performance/list.html'
    context_object_name = 'scores'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = PerformanceScore.objects.select_related('employee', 'project').all()
        employee_id = self.request.GET.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset.order_by('-period_end', '-overall_score')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employees'] = Employee.objects.all()
        return context


# ==================== NOTIFICATION MANAGEMENT ====================

class AdminNotificationListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Notification
    template_name = 'admin_custom/notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Notification.objects.select_related('user').all()
        level = self.request.GET.get('level')
        if level:
            queryset = queryset.filter(level=level)
        is_read = self.request.GET.get('is_read')
        if is_read:
            queryset = queryset.filter(is_read=is_read == 'true')
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_notifications'] = Notification.objects.count()
        context['unread_notifications'] = Notification.objects.filter(is_read=False).count()
        return context


# ==================== AI INSIGHTS MANAGEMENT ====================

class AdminAIInsightListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = AIInsight
    template_name = 'admin_custom/ai_insights/list.html'
    context_object_name = 'insights'
    paginate_by = 20
    
    def get_queryset(self):
        return AIInsight.objects.all().order_by('-created_at')


# ==================== EXPORT FUNCTIONS ====================

class AdminExportView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Base view cho export data."""
    pass


@login_required
@user_passes_test(is_staff_user)
def export_projects_csv(request):
    """Export projects to CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="projects.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Tên', 'Khách hàng', 'Trạng thái', 'Ưu tiên', 'Ngân sách dự kiến', 'Ngân sách thực tế', 'Ngày bắt đầu', 'Ngày kết thúc'])
    
    projects = Project.objects.select_related('client').all()
    for project in projects:
        writer.writerow([
            project.id,
            project.name,
            project.client.name if project.client else '',
            project.get_status_display(),
            project.get_priority_display(),
            project.estimated_budget,
            project.actual_budget,
            project.start_date or '',
            project.end_date or '',
        ])
    
    return response


@login_required
@user_passes_test(is_staff_user)
def export_employees_csv(request):
    """Export employees to CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Mã NV', 'Họ', 'Tên', 'Email', 'Phòng ban', 'Chức vụ', 'Loại hợp đồng', 'Lương/giờ', 'Trạng thái'])
    
    employees = Employee.objects.select_related('department').all()
    for emp in employees:
        writer.writerow([
            emp.id,
            emp.employee_id,
            emp.first_name,
            emp.last_name,
            emp.email,
            emp.department.name if emp.department else '',
            emp.position,
            emp.get_employment_type_display(),
            emp.hourly_rate,
            'Hoạt động' if emp.is_active else 'Không hoạt động',
        ])
    
    return response


@login_required
@user_passes_test(is_staff_user)
def export_clients_csv(request):
    """Export clients to CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clients.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Tên', 'Loại', 'Trạng thái', 'Email', 'Số điện thoại', 'Ngành nghề'])
    
    clients = Client.objects.all()
    for client in clients:
        writer.writerow([
            client.id,
            client.name,
            client.get_client_type_display(),
            client.get_status_display(),
            client.email,
            client.phone,
            client.industry,
        ])
    
    return response