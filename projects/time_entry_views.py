"""Views for Time Entry management."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import TimeEntry, Task
from .forms import TimeEntryForm
from resources.models import Employee


class TimeEntryCreateView(LoginRequiredMixin, CreateView):
    """Tạo ghi chép thời gian cho nhân viên."""
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'projects/time_entry_form.html'
    
    def get_success_url(self):
        return reverse_lazy('projects:my_tasks')
    
    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        
        # Lấy employee của user
        if hasattr(user, 'employee'):
            initial['employee'] = user.employee
        
        # Lấy task từ query parameter
        task_id = self.request.GET.get('task')
        if task_id:
            try:
                task = Task.objects.get(pk=task_id)
                initial['task'] = task
            except Task.DoesNotExist:
                pass
        
        # Mặc định là ngày hôm nay
        initial['date'] = timezone.now().date()
        
        return initial
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = self.request.user
        
        # Chỉ cho phép chọn tasks được gán cho nhân viên này
        if hasattr(user, 'employee'):
            kwargs['employee'] = user.employee
            kwargs['tasks'] = Task.objects.filter(assigned_to=user.employee)
        else:
            kwargs['tasks'] = Task.objects.none()
        
        return kwargs
    
    def form_valid(self, form):
        user = self.request.user
        
        # Đảm bảo employee là của user hiện tại
        if hasattr(user, 'employee'):
            form.instance.employee = user.employee
        else:
            messages.error(self.request, 'Bạn chưa được liên kết với nhân viên nào.')
            return self.form_invalid(form)
        
        # Kiểm tra task có được gán cho nhân viên này không
        task = form.instance.task
        if task.assigned_to != user.employee:
            messages.error(self.request, 'Bạn không có quyền ghi chép thời gian cho công việc này.')
            return self.form_invalid(form)
        
        messages.success(self.request, f'Đã ghi chép {form.instance.hours} giờ cho công việc "{task.name}".')
        return super().form_valid(form)


class MyTimeEntriesView(LoginRequiredMixin, ListView):
    """Danh sách ghi chép thời gian của nhân viên."""
    model = TimeEntry
    template_name = 'projects/my_time_entries.html'
    context_object_name = 'time_entries'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'employee'):
            return TimeEntry.objects.none()
        
        queryset = TimeEntry.objects.filter(employee=user.employee).select_related('task', 'task__project').order_by('-date', '-created_at')
        
        # Filter theo task nếu có
        task_id = self.request.GET.get('task')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        # Filter theo tháng nếu có
        month = self.request.GET.get('month')
        if month:
            try:
                year, month_num = month.split('-')
                queryset = queryset.filter(date__year=year, date__month=month_num)
            except:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if hasattr(user, 'employee'):
            # Tính tổng giờ trong tháng hiện tại
            now = timezone.now()
            month_entries = TimeEntry.objects.filter(
                employee=user.employee,
                date__year=now.year,
                date__month=now.month
            )
            context['monthly_total'] = sum(entry.hours for entry in month_entries)
            
            # Tính tổng giờ trong tuần hiện tại
            week_start = now.date() - timedelta(days=now.weekday())
            week_entries = TimeEntry.objects.filter(
                employee=user.employee,
                date__gte=week_start
            )
            context['weekly_total'] = sum(entry.hours for entry in week_entries)
        
        return context


class QuickLogTimeEntryView(LoginRequiredMixin, View):
    """API endpoint để nhanh chóng ghi chép thời gian từ task card."""
    
    def post(self, request, task_id):
        try:
            task = get_object_or_404(Task, pk=task_id)
            user = request.user
            
            if not hasattr(user, 'employee'):
                return JsonResponse({'success': False, 'error': 'Bạn chưa được liên kết với nhân viên nào.'}, status=400)
            
            employee = user.employee
            
            # Kiểm tra task có được gán cho nhân viên này không
            if task.assigned_to != employee:
                return JsonResponse({'success': False, 'error': 'Bạn không có quyền ghi chép thời gian cho công việc này.'}, status=403)
            
            # Xử lý cả POST form data và JSON
            if request.content_type == 'application/json':
                import json
                data = json.loads(request.body)
            else:
                data = request.POST
            
            hours = Decimal(str(data.get('hours', 0)))
            date_str = data.get('date')
            if date_str:
                from datetime import datetime
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = timezone.now().date()
            description = data.get('description', '')
            
            if hours <= 0:
                return JsonResponse({'success': False, 'error': 'Số giờ phải lớn hơn 0.'}, status=400)
            
            # Kiểm tra xem đã có entry cho task, employee, date này chưa
            existing_entry = TimeEntry.objects.filter(
                task=task,
                employee=employee,
                date=date
            ).first()
            
            if existing_entry:
                # Cập nhật entry hiện có
                existing_entry.hours += hours
                if description:
                    existing_entry.description += f"\n{description}"
                existing_entry.save()
                return JsonResponse({
                    'success': True,
                    'message': f'Đã cập nhật ghi chép: {existing_entry.hours} giờ',
                    'entry_id': existing_entry.id
                })
            else:
                # Tạo entry mới
                entry = TimeEntry.objects.create(
                    task=task,
                    employee=employee,
                    date=date,
                    hours=hours,
                    description=description,
                    created_by=user
                )
                return JsonResponse({
                    'success': True,
                    'message': f'Đã ghi chép {hours} giờ cho công việc "{task.name}"',
                    'entry_id': entry.id
                })
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class AutoLogTimeOnCompleteView(LoginRequiredMixin, View):
    """Tự động ghi chép thời gian khi nhân viên hoàn thành task."""
    
    def post(self, request, task_id):
        try:
            task = get_object_or_404(Task, pk=task_id)
            user = request.user
            
            if not hasattr(user, 'employee'):
                return JsonResponse({'success': False, 'error': 'Bạn chưa được liên kết với nhân viên nào.'}, status=400)
            
            employee = user.employee
            
            # Kiểm tra task có được gán cho nhân viên này không
            if task.assigned_to != employee:
                return JsonResponse({'success': False, 'error': 'Bạn không có quyền thực hiện hành động này.'}, status=403)
            
            # Kiểm tra task đã có started_at chưa
            if not task.started_at:
                return JsonResponse({
                    'success': False,
                    'error': 'Công việc chưa được bắt đầu. Vui lòng bắt đầu công việc trước khi hoàn thành.'
                }, status=400)
            
            # Tính thời gian làm việc từ started_at đến bây giờ
            now = timezone.now()
            duration = now - task.started_at
            hours_worked = Decimal(str(duration.total_seconds() / 3600)).quantize(Decimal('0.01'))
            
            if hours_worked <= 0:
                hours_worked = Decimal('0.5')  # Tối thiểu 0.5 giờ
            
            # Tạo hoặc cập nhật TimeEntry cho ngày hôm nay
            today = timezone.now().date()
            entry, created = TimeEntry.objects.get_or_create(
                task=task,
                employee=employee,
                date=today,
                defaults={
                    'hours': hours_worked,
                    'description': f'Tự động ghi chép khi hoàn thành công việc',
                    'created_by': user
                }
            )
            
            if not created:
                # Nếu đã có entry, cộng thêm giờ
                entry.hours += hours_worked
                entry.description += f"\nTự động cập nhật khi hoàn thành: +{hours_worked} giờ"
                entry.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Đã tự động ghi chép {hours_worked} giờ làm việc.',
                'hours': float(hours_worked),
                'entry_id': entry.id
            })
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
