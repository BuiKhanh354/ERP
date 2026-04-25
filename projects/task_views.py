"""Web views for Task Management (Checklist)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse

from .models import Task, Project, ProjectPhase
from .forms import TaskForm
from resources.models import Employee, Department
from core.mixins import ManagerRequiredMixin
from django.utils import timezone
from core.notification_service import NotificationService
from core.models import Notification
from .delay_kpi_service import DelayKPIService
from .task_history_service import TaskHistoryService
from core.rbac import get_user_role_names


def user_has_manager_capability(user):
    """RBAC-first manager check with legacy fallback."""
    role_names = get_user_role_names(user)
    if role_names.intersection({'ADMIN', 'MANAGER'}):
        return True
    return False


def user_can_approve_tasks(user):
    """Who can do final approval for submitted tasks."""
    role_names = get_user_role_names(user)
    if role_names.intersection({'ADMIN', 'MANAGER'}):
        return True
    return False


class TaskListView(LoginRequiredMixin, ListView):
    """Danh sách công việc dạng checklist cho project."""
    model = Task
    template_name = 'projects/tasks.html'
    context_object_name = 'tasks'
    
    def get_queryset(self):
        project_id = self.request.GET.get('project')
        user = self.request.user
        is_manager = user_has_manager_capability(user)
        
        # Lấy employee của user hiện tại (nếu có)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                if is_manager:
                    # Quản lý xem tất cả tasks của project
                    qs = Task.objects.filter(
                        project_id=project_id_int
                    )
                else:
                    # Nhân viên xem tasks được gán cho mình hoặc tasks của projects do mình tạo
                    qs = Task.objects.filter(
                        Q(project_id=project_id_int) & (
                            Q(assigned_to=employee) | Q(project__created_by=user)
                        )
                    )
                # Auto mark overdue: đã quá due_date hoặc quá estimated_end_at
                candidates = qs.filter(status__in=['todo', 'in_progress', 'review', 'overdue']).select_related('project', 'assigned_to')
                DelayKPIService.sync_overdue_tasks(candidates, actor=user)
                return qs.select_related('project', 'assigned_to', 'department').order_by('status', 'due_date', 'created_at')
            except (ValueError, TypeError):
                return Task.objects.none()
        return Task.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.request.GET.get('project')
        
        user = self.request.user
        is_manager = user_has_manager_capability(user)
        
        # Lấy employee của user hiện tại (nếu có)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                if is_manager:
                    # Quản lý xem tất cả projects
                    project = get_object_or_404(Project, pk=project_id_int)
                else:
                    # Nhân viên xem project được gán hoặc do mình tạo
                    project = get_object_or_404(
                        Project, 
                        pk=project_id_int
                    )
                context['project'] = project
                
                # Task stats
                tasks = self.get_queryset()
                context['total_tasks'] = tasks.count()
                context['todo_tasks'] = tasks.filter(status='todo').count()
                context['in_progress_tasks'] = tasks.filter(status='in_progress').count()
                context['review_tasks'] = tasks.filter(status='review').count()
                context['done_tasks'] = tasks.filter(status='done').count()
                context['completion_rate'] = (context['done_tasks'] / context['total_tasks'] * 100) if context['total_tasks'] > 0 else 0
            except (ValueError, TypeError):
                pass
        
        # Quản lý xem tất cả, nhân viên chỉ của mình
        if is_manager:
            context['projects'] = Project.objects.all()
            context['employees'] = Employee.objects.filter(is_active=True)
        else:
            # Nhân viên xem projects được gán cho mình hoặc do mình tạo
            if employee:
                context['projects'] = Project.objects.filter(
                    Q(allocations__employee=employee) | Q(created_by=user)
                ).distinct()
            else:
                context['projects'] = Project.objects.filter(created_by=user)
            context['employees'] = Employee.objects.filter(is_active=True, created_by=user)
        context['selected_project'] = project_id
        context['departments'] = Department.objects.all()
        
        return context


class TaskCreateView(ManagerRequiredMixin, CreateView):
    """Tạo công việc mới - chỉ quản lý."""
    model = Task
    form_class = TaskForm
    template_name = 'projects/task_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        project_id = self.request.GET.get('project')
        if project_id:
            try:
                kwargs['project'] = Project.objects.get(pk=int(project_id))
            except (Project.DoesNotExist, ValueError, TypeError):
                pass
        return kwargs
    
    def get_success_url(self):
        project_id = self.request.GET.get('project') or self.object.project.pk
        from_page = self.request.GET.get('from', 'tasks')
        
        if from_page == 'detail':
            # Nếu đến từ trang chi tiết dự án, quay về đó
            return reverse_lazy('projects:detail', kwargs={'pk': project_id})
        else:
            # Nếu đến từ trang công việc, quay về đó
            return reverse_lazy('projects:tasks') + f'?project={project_id}'
    
    def form_valid(self, form):
        project_id = self.request.GET.get('project')
        user = self.request.user
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                # Quản lý có thể tạo task cho bất kỳ project nào
                form.instance.project = get_object_or_404(Project, pk=project_id_int)
            except (ValueError, TypeError):
                pass
        if form.instance.priority == 'critical' and not DelayKPIService.can_assign_critical_task(user):
            form.add_error(None, 'KPI hien tai duoi nguong 70, ban khong duoc phep giao task quan trong.')
            return self.form_invalid(form)
        if form.instance.priority == 'critical' and form.instance.assigned_to:
            if form.instance.assigned_to.kpi_current < 70:
                form.add_error('assigned_to', 'Nhan su duoc giao task critical phai co KPI >= 70.')
                return self.form_invalid(form)
        TaskHistoryService.update_task_snapshots(form.instance)
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        DelayKPIService.update_task_delay_metrics(self.object, actor=user)
        TaskHistoryService.log(self.object, actor=user, event_type='created', note='Task created')
        if self.object.assigned_to_id:
            TaskHistoryService.log(self.object, actor=user, event_type='assigned', note='Task assigned to employee')

        # Thông báo cho nhân viên được giao việc (nếu có)
        try:
            task = self.object
            assigned_emp = getattr(task, "assigned_to", None)
            assigned_user = getattr(assigned_emp, "user", None) if assigned_emp else None
            if assigned_user:
                NotificationService.notify(
                    user=assigned_user,
                    title=f"Bạn được giao công việc: {task.name}",
                    message=f"Bạn được giao công việc \"{task.name}\" trong dự án \"{task.project.name}\".",
                    level=Notification.LEVEL_INFO,
                    url=f"/projects/tasks/{task.pk}/edit/",
                    actor=self.request.user,
                )
        except Exception:
            pass

        messages.success(self.request, f'Đã tạo công việc "{form.instance.name}" thành công.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_manager = user_has_manager_capability(user)
        
        context['page_title'] = 'Tạo công việc mới'
        context['submit_text'] = 'Tạo công việc'
        if is_manager:
            context['projects'] = Project.objects.all()
            context['employees'] = Employee.objects.filter(is_active=True)
        else:
            context['projects'] = Project.objects.filter(created_by=user)
            context['employees'] = Employee.objects.filter(is_active=True, created_by=user)
        context['selected_project'] = self.request.GET.get('project')
        context['departments'] = Department.objects.all()
        
        # Xác định nguồn (từ detail hay từ tasks)
        context['from_page'] = self.request.GET.get('from', 'tasks')
        context['back_url'] = None
        
        if context['from_page'] == 'detail':
            # Nếu đến từ trang chi tiết, quay về đó
            project_id = self.request.GET.get('project')
            if project_id:
                context['back_url'] = reverse_lazy('projects:detail', kwargs={'pk': project_id})
        else:
            # Nếu đến từ trang công việc, quay về đó
            project_id = self.request.GET.get('project')
            if project_id:
                context['back_url'] = reverse_lazy('projects:tasks') + f'?project={project_id}'
            else:
                context['back_url'] = reverse_lazy('projects:tasks')
        
        # Set initial employees based on selected department (if any)
        department_id = self.request.GET.get('department')
        if department_id:
            try:
                department = Department.objects.get(pk=department_id)
                context['initial_employees'] = Employee.objects.filter(
                    department=department, is_active=True
                )
            except Department.DoesNotExist:
                context['initial_employees'] = Employee.objects.none()
        else:
            context['initial_employees'] = Employee.objects.none()
        
        return context


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    """Cập nhật công việc - quản lý có thể sửa, nhân viên chỉ xem."""
    model = Task
    form_class = TaskForm
    template_name = 'projects/task_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        task = self.get_object()
        if task.project_id:
            kwargs['project'] = task.project
        return kwargs
    
    def get_queryset(self):
        """Quản lý xem tất cả, nhân viên chỉ xem tasks được gán cho mình."""
        user = self.request.user
        is_manager = user_has_manager_capability(user)
        
        if is_manager:
            return Task.objects.all()
        else:
            # Nhân viên chỉ xem tasks được gán cho mình
            employee = getattr(user, 'employee', None)
            if employee:
                return Task.objects.filter(assigned_to=employee)
            return Task.objects.none()
    
    def dispatch(self, request, *args, **kwargs):
        """Kiểm tra quyền trước khi xử lý request."""
        response = super().dispatch(request, *args, **kwargs)
        user = request.user
        is_manager = user_has_manager_capability(user)
        
        # Nếu không phải quản lý, chỉ cho phép GET (xem), không cho POST (sửa)
        if not is_manager and request.method == 'POST':
            from django.contrib import messages
            messages.error(request, 'Bạn không có quyền chỉnh sửa công việc này.')
            return redirect('projects:my_tasks')
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('projects:tasks') + f'?project={self.object.project.pk}'
    
    def form_valid(self, form):
        user = self.request.user
        is_manager = user_has_manager_capability(user)

        # Lưu lại assigned_to cũ để detect thay đổi
        old_task = self.get_object()
        old_assigned_id = old_task.assigned_to_id

        if form.instance.priority == 'critical' and not DelayKPIService.can_assign_critical_task(user):
            form.add_error(None, 'KPI hien tai duoi nguong 70, ban khong duoc phep giao task quan trong.')
            return self.form_invalid(form)
        if form.instance.priority == 'critical' and form.instance.assigned_to:
            if form.instance.assigned_to.kpi_current < 70:
                form.add_error('assigned_to', 'Nhan su duoc giao task critical phai co KPI >= 70.')
                return self.form_invalid(form)

        TaskHistoryService.update_task_snapshots(form.instance)
        form.instance.updated_by = user
        response = super().form_valid(form)
        DelayKPIService.update_task_delay_metrics(self.object, actor=user)
        TaskHistoryService.log(self.object, actor=user, event_type='updated', note='Task updated')

        # Nếu quản lý đổi người được giao -> thông báo cho người mới
        if is_manager:
            try:
                task = self.object
                new_assigned_id = task.assigned_to_id
                if new_assigned_id and new_assigned_id != old_assigned_id:
                    assigned_emp = task.assigned_to
                    assigned_user = getattr(assigned_emp, "user", None) if assigned_emp else None
                    TaskHistoryService.log(task, actor=user, event_type='assigned', note='Assignee changed')
                    if assigned_user:
                        NotificationService.notify(
                            user=assigned_user,
                            title=f"Bạn được giao công việc: {task.name}",
                            message=f"Bạn được giao công việc \"{task.name}\" trong dự án \"{task.project.name}\".",
                            level=Notification.LEVEL_INFO,
                            url=f"/projects/tasks/{task.pk}/edit/",
                            actor=user,
                        )
            except Exception:
                pass

        messages.success(self.request, f'Đã cập nhật công việc "{form.instance.name}" thành công.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_manager = user_has_manager_capability(user)
        
        task = self.get_object()
        
        # Nhân viên chỉ xem, không sửa
        if is_manager:
            context['page_title'] = f'Chỉnh sửa: {task.name}'
            context['submit_text'] = 'Cập nhật'
            context['is_readonly'] = False
        else:
            context['page_title'] = f'Chi tiết công việc: {task.name}'
            context['submit_text'] = 'Cập nhật'
            context['is_readonly'] = True  # Chế độ chỉ đọc cho nhân viên
        
        if is_manager:
            context['projects'] = Project.objects.all()
            context['employees'] = Employee.objects.filter(is_active=True)
        else:
            context['projects'] = Project.objects.filter(created_by=user)
            context['employees'] = Employee.objects.filter(is_active=True, created_by=user)
        context['departments'] = Department.objects.all()
        
        # Set initial employees based on task's department
        if task.department:
            context['initial_employees'] = Employee.objects.filter(
                department=task.department, is_active=True
            )
        else:
            context['initial_employees'] = Employee.objects.none()
        
        # Thêm back URL cho nhân viên
        if not is_manager:
            context['back_url'] = reverse_lazy('projects:my_tasks')
        
        return context


class TaskDeleteView(ManagerRequiredMixin, DeleteView):
    """Xóa công việc - chỉ quản lý."""
    model = Task
    
    def get_queryset(self):
        """Quản lý có thể xóa tất cả."""
        return Task.objects.all()
    
    def get_success_url(self):
        return reverse_lazy('projects:tasks') + f'?project={self.object.project.pk}'
    
    def delete(self, request, *args, **kwargs):
        task = self.get_object()
        messages.success(request, f'Đã xóa công việc "{task.name}".')
        return super().delete(request, *args, **kwargs)


class TaskUpdateStatusView(LoginRequiredMixin, View):
    """Cập nhật trạng thái công việc (AJAX) - quản lý và nhân viên đều được phép."""
    def post(self, request, pk):
        from django.http import JsonResponse
        import json
        
        user = request.user
        is_manager = user_has_manager_capability(user)
        
        # Lấy employee của user hiện tại (nếu có)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if is_manager:
            task = get_object_or_404(Task, pk=pk)
            if not DelayKPIService.can_approve_others(user):
                return JsonResponse({'success': False, 'error': 'KPI duoi nguong. Ban khong duoc phe duyet task cua nguoi khac.'}, status=403)
        else:
            # Nhân viên chỉ cập nhật tasks được gán cho mình hoặc tasks của projects do mình tạo
            try:
                task = Task.objects.filter(
                    Q(assigned_to=employee) | Q(project__created_by=user)
                ).get(pk=pk)
            except Task.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Không tìm thấy công việc.'})
        
        data = json.loads(request.body)
        action = data.get('action')
        new_status = data.get('status')

        # Two-step approval:
        # employee submits to review, manager approves/rejects from review
        if action == 'approve':
            if not user_can_approve_tasks(user):
                return JsonResponse({'success': False, 'error': 'Bạn không có quyền duyệt công việc.'}, status=403)
            if task.status != 'review':
                return JsonResponse({'success': False, 'error': 'Chỉ duyệt được task đang ở trạng thái Review.'}, status=400)
            new_status = 'done'
        elif action == 'reject':
            if not user_can_approve_tasks(user):
                return JsonResponse({'success': False, 'error': 'Bạn không có quyền từ chối công việc.'}, status=403)
            if task.status != 'review':
                return JsonResponse({'success': False, 'error': 'Chỉ từ chối được task đang ở trạng thái Review.'}, status=400)
            new_status = 'in_progress'
            task.assignment_status = 'rejected'
        
        if new_status not in dict(Task.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Trạng thái không hợp lệ.'})

        if not is_manager and new_status == 'done':
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Nhân viên không thể tự chuyển trực tiếp sang Done. Hãy gửi Review để quản lý duyệt.',
                },
                status=403,
            )
        if is_manager and new_status == 'done' and task.status != 'review':
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Task chỉ được chuyển Done sau bước Review.',
                },
                status=400,
            )
        
        task.status = new_status
        if new_status == 'done' and not task.completed_at:
            task.completed_at = timezone.now()
        task.save()
        DelayKPIService.update_task_delay_metrics(task, actor=user)
        TaskHistoryService.log(task, actor=user, event_type='status_changed', note=f'Status changed to {new_status}')
        
        return JsonResponse({
            'success': True,
            'status': task.status,
            'status_display': task.get_status_display()
        })


class GetEmployeesByDepartmentView(LoginRequiredMixin, View):
    """API endpoint để lấy danh sách nhân viên theo phòng ban (AJAX)."""
    def get(self, request):
        department_id = request.GET.get('department_id')
        project_id = request.GET.get('project_id')
        if not department_id:
            return JsonResponse({'employees': []})
        
        try:
            department = Department.objects.get(pk=department_id)
            employees = Employee.objects.filter(
                department=department, 
                is_active=True
            )
            if project_id:
                employees = employees.filter(allocations__project_id=project_id).distinct()
            employees = employees.values('id', 'first_name', 'last_name', 'employee_id')
            
            employees_list = [
                {
                    'id': emp['id'],
                    'name': f"{emp['first_name']} {emp['last_name']}",
                    'employee_id': emp['employee_id']
                }
                for emp in employees
            ]
            
            return JsonResponse({'employees': employees_list})
        except Department.DoesNotExist:
            return JsonResponse({'employees': []})


class UpdateAssignmentStatusView(LoginRequiredMixin, View):
    """Cập nhật trạng thái giao/nhận việc (AJAX)."""
    def post(self, request, pk):
        import json
        from django.utils import timezone
        user = request.user
        employee = None
        
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if not employee:
            return JsonResponse({'success': False, 'error': 'Bạn không phải là nhân viên.'})
        
        # Chỉ cho phép nhân viên được gán công việc cập nhật trạng thái
        task = get_object_or_404(Task, pk=pk, assigned_to=employee)
        
        data = json.loads(request.body)
        new_status = data.get('assignment_status')
        
        if new_status not in dict(Task.ASSIGNMENT_STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Trạng thái không hợp lệ.'})
        
        task.assignment_status = new_status
        if new_status == 'in_progress' and task.started_at is None:
            task.started_at = timezone.now()
            task.status = 'in_progress'
        elif new_status == 'accepted' and task.status == 'done':
            task.status = 'todo'
        elif new_status == 'completed':
            # Employee submits completion for manager review.
            task.status = 'review'
            task.completed_at = None
        elif new_status == 'rejected' and task.status == 'in_progress':
            task.status = 'todo'
        TaskHistoryService.update_task_snapshots(task)
        task.save()
        DelayKPIService.update_task_delay_metrics(task, actor=user)
        event_map = {
            'accepted': 'accepted',
            'in_progress': 'in_progress',
            'completed': 'completed',
            'rejected': 'rejected',
            'assigned': 'assigned',
        }
        TaskHistoryService.log(
            task,
            actor=user,
            event_type=event_map.get(new_status, 'updated'),
            note=f'Assignment status changed to {new_status}'
        )
        
        return JsonResponse({
            'success': True,
            'assignment_status': task.assignment_status,
            'assignment_status_display': task.get_assignment_status_display(),
            'task_status': task.status,
            'task_status_display': task.get_status_display()
        })


class MyTasksView(LoginRequiredMixin, ListView):
    """Trang xem công việc được gán cho user hiện tại."""
    model = Task
    template_name = 'projects/my_tasks.html'
    context_object_name = 'tasks'
    
    def get_queryset(self):
        user = self.request.user
        employee = None
        
        # Lấy employee của user hiện tại
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if not employee:
            return Task.objects.none()
        
        # Lấy tất cả tasks được gán cho employee này
        queryset = Task.objects.filter(
            assigned_to=employee
        ).select_related('project', 'department').order_by('-due_date', '-created_at')
        
        # Filter theo trạng thái nếu có
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter theo trạng thái giao/nhận nếu có
        assignment_status_filter = self.request.GET.get('assignment_status')
        if assignment_status_filter:
            queryset = queryset.filter(assignment_status=assignment_status_filter)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        employee = None
        
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if employee:
            tasks = self.get_queryset()
            context['total_tasks'] = tasks.count()
            context['assigned_tasks'] = tasks.filter(assignment_status='assigned').count()
            context['accepted_tasks'] = tasks.filter(assignment_status='accepted').count()
            context['in_progress_tasks'] = tasks.filter(assignment_status='in_progress').count()
            context['completed_tasks'] = tasks.filter(assignment_status='completed').count()
            context['rejected_tasks'] = tasks.filter(assignment_status='rejected').count()
            
            # Stats theo status
            context['todo_tasks'] = tasks.filter(status='todo').count()
            context['in_progress_status_tasks'] = tasks.filter(status='in_progress').count()
            context['review_tasks'] = tasks.filter(status='review').count()
            context['done_tasks'] = tasks.filter(status='done').count()
        
        context['status_filter'] = self.request.GET.get('status', '')
        context['assignment_status_filter'] = self.request.GET.get('assignment_status', '')
        
        return context




class PhaseDateSuggestionView(LoginRequiredMixin, View):
    """Suggest task start/end dates constrained by selected phase timeline."""

    def get(self, request, *args, **kwargs):
        phase_id = request.GET.get('phase_id')
        if not phase_id:
            return JsonResponse({'ok': False, 'error': 'phase_id is required'}, status=400)

        try:
            phase = ProjectPhase.objects.select_related('project').get(pk=int(phase_id))
        except (ValueError, ProjectPhase.DoesNotExist):
            return JsonResponse({'ok': False, 'error': 'Phase not found'}, status=404)

        phase_start = phase.start_date
        phase_end = phase.end_date
        if not phase_start or not phase_end:
            return JsonResponse({
                'ok': True,
                'suggested_start_date': None,
                'suggested_due_date': None,
                'message': 'Phase chua co day du ngay bat dau/ket thuc.',
            })

        estimated_hours_raw = (request.GET.get('estimated_hours') or '').strip()
        try:
            estimated_hours = float(estimated_hours_raw) if estimated_hours_raw else 0.0
        except ValueError:
            estimated_hours = 0.0

        estimated_days = max(1, int(round(estimated_hours / 8.0))) if estimated_hours > 0 else 2

        latest_due = (
            Task.objects.filter(phase=phase, due_date__isnull=False)
            .order_by('-due_date')
            .values_list('due_date', flat=True)
            .first()
        )
        suggested_start = (latest_due + timedelta(days=1)) if latest_due else phase_start
        if suggested_start < phase_start:
            suggested_start = phase_start
        if suggested_start > phase_end:
            suggested_start = phase_end

        suggested_due = suggested_start + timedelta(days=estimated_days - 1)
        if suggested_due > phase_end:
            suggested_due = phase_end
        if suggested_due < suggested_start:
            suggested_due = suggested_start

        return JsonResponse({
            'ok': True,
            'phase_start': phase_start.isoformat(),
            'phase_end': phase_end.isoformat(),
            'suggested_start_date': suggested_start.isoformat(),
            'suggested_due_date': suggested_due.isoformat(),
            'estimated_days': estimated_days,
        })
