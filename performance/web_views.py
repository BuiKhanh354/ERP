"""
Web views for Performance Score management (non-admin interface).
"""
from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Avg
from django.contrib import messages
from .models import PerformanceScore
from .forms import PerformanceScoreForm
from resources.models import Employee
from core.mixins import ManagerRequiredMixin


class PerformanceScoreCreateView(ManagerRequiredMixin, CreateView):
    """Tạo đánh giá hiệu suất mới - chỉ quản lý."""
    model = PerformanceScore
    form_class = PerformanceScoreForm
    template_name = 'performance/score_form.html'

    def get_initial(self):
        """Set employee từ query parameter."""
        initial = super().get_initial()
        employee_id = self.request.GET.get('employee')
        if employee_id:
            initial['employee'] = employee_id
        return initial

    def get_form(self, form_class=None):
        """Customize form để ẩn employee field nếu đã có trong URL."""
        form = super().get_form(form_class)
        employee_id = self.request.GET.get('employee')
        if employee_id:
            # Ẩn field employee và set giá trị
            form.fields['employee'].widget = form.fields['employee'].hidden_widget()
            try:
                employee = Employee.objects.get(pk=employee_id)
                form.instance.employee = employee
            except Employee.DoesNotExist:
                pass
        else:
            # Nếu không có employee trong URL, chỉ hiển thị employees mà user có quyền quản lý
            if hasattr(self.request.user, 'profile') and self.request.user.profile.is_manager():
                # Manager xem tất cả
                pass
            else:
                # Nhân viên chỉ xem của mình
                form.fields['employee'].queryset = Employee.objects.filter(
                    user=self.request.user
                )
        return form

    def get_context_data(self, **kwargs):
        """Thêm employee và back_url vào context."""
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee')
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
                context['employee'] = employee
                context['back_url'] = reverse('resources:detail', kwargs={'pk': employee_id})
            except Employee.DoesNotExist:
                pass
        return context

    def form_valid(self, form):
        """Set created_by và tính overall_score nếu chưa có."""
        form.instance.created_by = self.request.user
        # Nếu overall_score chưa được set, tính từ các score khác
        if not form.instance.overall_score or form.instance.overall_score == 0:
            efficiency = form.instance.efficiency_score or 0
            quality = form.instance.quality_score or 0
            productivity = form.instance.productivity_score or 0
            form.instance.overall_score = (efficiency + quality + productivity) / 3
        messages.success(self.request, 'Đã tạo đánh giá hiệu suất thành công.')
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect về trang chi tiết nhân sự."""
        employee_id = self.object.employee.pk
        return reverse('resources:detail', kwargs={'pk': employee_id})


class PerformanceScoreUpdateView(ManagerRequiredMixin, UpdateView):
    """Cập nhật đánh giá hiệu suất - chỉ quản lý."""
    model = PerformanceScore
    form_class = PerformanceScoreForm
    template_name = 'performance/score_form.html'

    def get_queryset(self):
        """Chỉ cho phép sửa đánh giá mà user đã tạo hoặc là manager."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return PerformanceScore.objects.all()
        return PerformanceScore.objects.filter(created_by=user)

    def get_context_data(self, **kwargs):
        """Thêm back_url vào context."""
        context = super().get_context_data(**kwargs)
        employee_id = self.object.employee.pk if hasattr(self, 'object') and self.object else None
        if employee_id:
            context['back_url'] = reverse('resources:detail', kwargs={'pk': employee_id})
        return context

    def form_valid(self, form):
        """Set updated_by và tính overall_score nếu chưa có."""
        form.instance.updated_by = self.request.user
        # Nếu overall_score chưa được set, tính từ các score khác
        if not form.instance.overall_score or form.instance.overall_score == 0:
            efficiency = form.instance.efficiency_score or 0
            quality = form.instance.quality_score or 0
            productivity = form.instance.productivity_score or 0
            form.instance.overall_score = (efficiency + quality + productivity) / 3
        messages.success(self.request, 'Đã cập nhật đánh giá hiệu suất thành công.')
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect về trang chi tiết nhân sự."""
        employee_id = self.object.employee.pk
        return reverse('resources:detail', kwargs={'pk': employee_id})


class PerformanceScoreDeleteView(ManagerRequiredMixin, DeleteView):
    """Xóa đánh giá hiệu suất - chỉ quản lý."""
    model = PerformanceScore

    def get_queryset(self):
        """Chỉ cho phép xóa đánh giá mà user đã tạo hoặc là manager."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return PerformanceScore.objects.all()
        return PerformanceScore.objects.filter(created_by=user)

    def delete(self, request, *args, **kwargs):
        """Override để lưu employee_id trước khi xóa."""
        self.object = self.get_object()
        employee_id = self.object.employee.pk
        messages.success(request, 'Đã xóa đánh giá hiệu suất thành công.')
        response = super().delete(request, *args, **kwargs)
        return response

    def get_success_url(self):
        """Redirect về trang chi tiết nhân sự."""
        employee_id = self.request.GET.get('employee') or self.object.employee.pk
        return reverse('resources:detail', kwargs={'pk': employee_id})


class PerformanceScoreListView(ManagerRequiredMixin, ListView):
    """Danh sách đánh giá hiệu suất - chỉ quản lý."""
    model = PerformanceScore
    template_name = 'performance/score_list.html'
    context_object_name = 'scores'
    paginate_by = 20

    def get_queryset(self):
        """Filter theo employee nếu có query parameter."""
        queryset = PerformanceScore.objects.select_related('employee', 'project', 'created_by').order_by('-period_end', '-created_at')
        employee_id = self.request.GET.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee')
        if employee_id:
            context['employee'] = get_object_or_404(Employee, pk=employee_id)
        return context
