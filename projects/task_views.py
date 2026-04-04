"""Web views for Task Management (Checklist)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse

from .models import Task, Project
from .forms import TaskForm
from resources.models import Employee, Department
from core.mixins import ManagerRequiredMixin
from django.utils import timezone
from core.notification_service import NotificationService
from core.models import Notification
from .delay_kpi_service import DelayKPIService
from .task_history_service import TaskHistoryService


class TaskListView(LoginRequiredMixin, ListView):
    """Danh sÃƒÂ¡ch cÃƒÂ´ng viÃ¡Â»â€¡c dÃ¡ÂºÂ¡ng checklist cho project."""
    model = Task
    template_name = 'projects/tasks.html'
    context_object_name = 'tasks'
    
    def get_queryset(self):
        project_id = self.request.GET.get('project')
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        # LÃ¡ÂºÂ¥y employee cÃ¡Â»Â§a user hiÃ¡Â»â€¡n tÃ¡ÂºÂ¡i (nÃ¡ÂºÂ¿u cÃƒÂ³)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                if is_manager:
                    # QuÃ¡ÂºÂ£n lÃƒÂ½ xem tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£ tasks cÃ¡Â»Â§a project
                    qs = Task.objects.filter(
                        project_id=project_id_int
                    )
                else:
                    # NhÃƒÂ¢n viÃƒÂªn xem tasks Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho mÃƒÂ¬nh hoÃ¡ÂºÂ·c tasks cÃ¡Â»Â§a projects do mÃƒÂ¬nh tÃ¡ÂºÂ¡o
                    qs = Task.objects.filter(
                        Q(project_id=project_id_int) & (
                            Q(assigned_to=employee) | Q(project__created_by=user)
                        )
                    )
                # Auto mark overdue: Ã„â€˜ÃƒÂ£ quÃƒÂ¡ due_date hoÃ¡ÂºÂ·c quÃƒÂ¡ estimated_end_at
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
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        # LÃ¡ÂºÂ¥y employee cÃ¡Â»Â§a user hiÃ¡Â»â€¡n tÃ¡ÂºÂ¡i (nÃ¡ÂºÂ¿u cÃƒÂ³)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                if is_manager:
                    # QuÃ¡ÂºÂ£n lÃƒÂ½ xem tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£ projects
                    project = get_object_or_404(Project, pk=project_id_int)
                else:
                    # NhÃƒÂ¢n viÃƒÂªn xem project Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n hoÃ¡ÂºÂ·c do mÃƒÂ¬nh tÃ¡ÂºÂ¡o
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
        
        # QuÃ¡ÂºÂ£n lÃƒÂ½ xem tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£, nhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° cÃ¡Â»Â§a mÃƒÂ¬nh
        if is_manager:
            context['projects'] = Project.objects.all()
            context['employees'] = Employee.objects.filter(is_active=True)
        else:
            # NhÃƒÂ¢n viÃƒÂªn xem projects Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho mÃƒÂ¬nh hoÃ¡ÂºÂ·c do mÃƒÂ¬nh tÃ¡ÂºÂ¡o
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
    """TÃ¡ÂºÂ¡o cÃƒÂ´ng viÃ¡Â»â€¡c mÃ¡Â»â€ºi - chÃ¡Â»â€° quÃ¡ÂºÂ£n lÃƒÂ½."""
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
            # NÃ¡ÂºÂ¿u Ã„â€˜Ã¡ÂºÂ¿n tÃ¡Â»Â« trang chi tiÃ¡ÂºÂ¿t dÃ¡Â»Â± ÃƒÂ¡n, quay vÃ¡Â»Â Ã„â€˜ÃƒÂ³
            return reverse_lazy('projects:detail', kwargs={'pk': project_id})
        else:
            # NÃ¡ÂºÂ¿u Ã„â€˜Ã¡ÂºÂ¿n tÃ¡Â»Â« trang cÃƒÂ´ng viÃ¡Â»â€¡c, quay vÃ¡Â»Â Ã„â€˜ÃƒÂ³
            return reverse_lazy('projects:tasks') + f'?project={project_id}'
    
    def form_valid(self, form):
        project_id = self.request.GET.get('project')
        user = self.request.user
        
        if project_id and project_id != 'None' and project_id.strip():
            try:
                project_id_int = int(project_id)
                # QuÃ¡ÂºÂ£n lÃƒÂ½ cÃƒÂ³ thÃ¡Â»Æ’ tÃ¡ÂºÂ¡o task cho bÃ¡ÂºÂ¥t kÃ¡Â»Â³ project nÃƒÂ o
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

        # ThÃƒÂ´ng bÃƒÂ¡o cho nhÃƒÂ¢n viÃƒÂªn Ã„â€˜Ã†Â°Ã¡Â»Â£c giao viÃ¡Â»â€¡c (nÃ¡ÂºÂ¿u cÃƒÂ³)
        try:
            task = self.object
            assigned_emp = getattr(task, "assigned_to", None)
            assigned_user = getattr(assigned_emp, "user", None) if assigned_emp else None
            if assigned_user:
                NotificationService.notify(
                    user=assigned_user,
                    title=f"BÃ¡ÂºÂ¡n Ã„â€˜Ã†Â°Ã¡Â»Â£c giao cÃƒÂ´ng viÃ¡Â»â€¡c: {task.name}",
                    message=f"BÃ¡ÂºÂ¡n Ã„â€˜Ã†Â°Ã¡Â»Â£c giao cÃƒÂ´ng viÃ¡Â»â€¡c \"{task.name}\" trong dÃ¡Â»Â± ÃƒÂ¡n \"{task.project.name}\".",
                    level=Notification.LEVEL_INFO,
                    url=f"/projects/tasks/{task.pk}/edit/",
                    actor=self.request.user,
                )
        except Exception:
            pass

        messages.success(self.request, f'Ã„ÂÃƒÂ£ tÃ¡ÂºÂ¡o cÃƒÂ´ng viÃ¡Â»â€¡c "{form.instance.name}" thÃƒÂ nh cÃƒÂ´ng.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        context['page_title'] = 'TÃ¡ÂºÂ¡o cÃƒÂ´ng viÃ¡Â»â€¡c mÃ¡Â»â€ºi'
        context['submit_text'] = 'TÃ¡ÂºÂ¡o cÃƒÂ´ng viÃ¡Â»â€¡c'
        if is_manager:
            context['projects'] = Project.objects.all()
            context['employees'] = Employee.objects.filter(is_active=True)
        else:
            context['projects'] = Project.objects.filter(created_by=user)
            context['employees'] = Employee.objects.filter(is_active=True, created_by=user)
        context['selected_project'] = self.request.GET.get('project')
        context['departments'] = Department.objects.all()
        
        # XÃƒÂ¡c Ã„â€˜Ã¡Â»â€¹nh nguÃ¡Â»â€œn (tÃ¡Â»Â« detail hay tÃ¡Â»Â« tasks)
        context['from_page'] = self.request.GET.get('from', 'tasks')
        context['back_url'] = None
        
        if context['from_page'] == 'detail':
            # NÃ¡ÂºÂ¿u Ã„â€˜Ã¡ÂºÂ¿n tÃ¡Â»Â« trang chi tiÃ¡ÂºÂ¿t, quay vÃ¡Â»Â Ã„â€˜ÃƒÂ³
            project_id = self.request.GET.get('project')
            if project_id:
                context['back_url'] = reverse_lazy('projects:detail', kwargs={'pk': project_id})
        else:
            # NÃ¡ÂºÂ¿u Ã„â€˜Ã¡ÂºÂ¿n tÃ¡Â»Â« trang cÃƒÂ´ng viÃ¡Â»â€¡c, quay vÃ¡Â»Â Ã„â€˜ÃƒÂ³
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
    """CÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t cÃƒÂ´ng viÃ¡Â»â€¡c - quÃ¡ÂºÂ£n lÃƒÂ½ cÃƒÂ³ thÃ¡Â»Æ’ sÃ¡Â»Â­a, nhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° xem."""
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
        """QuÃ¡ÂºÂ£n lÃƒÂ½ xem tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£, nhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° xem tasks Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho mÃƒÂ¬nh."""
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if is_manager:
            return Task.objects.all()
        else:
            # NhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° xem tasks Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho mÃƒÂ¬nh
            employee = getattr(user, 'employee', None)
            if employee:
                return Task.objects.filter(assigned_to=employee)
            return Task.objects.none()
    
    def dispatch(self, request, *args, **kwargs):
        """KiÃ¡Â»Æ’m tra quyÃ¡Â»Ân trÃ†Â°Ã¡Â»â€ºc khi xÃ¡Â»Â­ lÃƒÂ½ request."""
        response = super().dispatch(request, *args, **kwargs)
        user = request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        # NÃ¡ÂºÂ¿u khÃƒÂ´ng phÃ¡ÂºÂ£i quÃ¡ÂºÂ£n lÃƒÂ½, chÃ¡Â»â€° cho phÃƒÂ©p GET (xem), khÃƒÂ´ng cho POST (sÃ¡Â»Â­a)
        if not is_manager and request.method == 'POST':
            from django.contrib import messages
            messages.error(request, 'BÃ¡ÂºÂ¡n khÃƒÂ´ng cÃƒÂ³ quyÃ¡Â»Ân chÃ¡Â»â€°nh sÃ¡Â»Â­a cÃƒÂ´ng viÃ¡Â»â€¡c nÃƒÂ y.')
            return redirect('projects:my_tasks')
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('projects:tasks') + f'?project={self.object.project.pk}'
    
    def form_valid(self, form):
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()

        # LÃ†Â°u lÃ¡ÂºÂ¡i assigned_to cÃ…Â© Ã„â€˜Ã¡Â»Æ’ detect thay Ã„â€˜Ã¡Â»â€¢i
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

        # NÃ¡ÂºÂ¿u quÃ¡ÂºÂ£n lÃƒÂ½ Ã„â€˜Ã¡Â»â€¢i ngÃ†Â°Ã¡Â»Âi Ã„â€˜Ã†Â°Ã¡Â»Â£c giao -> thÃƒÂ´ng bÃƒÂ¡o cho ngÃ†Â°Ã¡Â»Âi mÃ¡Â»â€ºi
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
                            title=f"BÃ¡ÂºÂ¡n Ã„â€˜Ã†Â°Ã¡Â»Â£c giao cÃƒÂ´ng viÃ¡Â»â€¡c: {task.name}",
                            message=f"BÃ¡ÂºÂ¡n Ã„â€˜Ã†Â°Ã¡Â»Â£c giao cÃƒÂ´ng viÃ¡Â»â€¡c \"{task.name}\" trong dÃ¡Â»Â± ÃƒÂ¡n \"{task.project.name}\".",
                            level=Notification.LEVEL_INFO,
                            url=f"/projects/tasks/{task.pk}/edit/",
                            actor=user,
                        )
            except Exception:
                pass

        messages.success(self.request, f'Ã„ÂÃƒÂ£ cÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t cÃƒÂ´ng viÃ¡Â»â€¡c "{form.instance.name}" thÃƒÂ nh cÃƒÂ´ng.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        task = self.get_object()
        
        # NhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° xem, khÃƒÂ´ng sÃ¡Â»Â­a
        if is_manager:
            context['page_title'] = f'ChÃ¡Â»â€°nh sÃ¡Â»Â­a: {task.name}'
            context['submit_text'] = 'CÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t'
            context['is_readonly'] = False
        else:
            context['page_title'] = f'Chi tiÃ¡ÂºÂ¿t cÃƒÂ´ng viÃ¡Â»â€¡c: {task.name}'
            context['submit_text'] = 'CÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t'
            context['is_readonly'] = True  # ChÃ¡ÂºÂ¿ Ã„â€˜Ã¡Â»â„¢ chÃ¡Â»â€° Ã„â€˜Ã¡Â»Âc cho nhÃƒÂ¢n viÃƒÂªn
        
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
        
        # ThÃƒÂªm back URL cho nhÃƒÂ¢n viÃƒÂªn
        if not is_manager:
            context['back_url'] = reverse_lazy('projects:my_tasks')
        
        return context


class TaskDeleteView(ManagerRequiredMixin, DeleteView):
    """XÃƒÂ³a cÃƒÂ´ng viÃ¡Â»â€¡c - chÃ¡Â»â€° quÃ¡ÂºÂ£n lÃƒÂ½."""
    model = Task
    
    def get_queryset(self):
        """QuÃ¡ÂºÂ£n lÃƒÂ½ cÃƒÂ³ thÃ¡Â»Æ’ xÃƒÂ³a tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£."""
        return Task.objects.all()
    
    def get_success_url(self):
        return reverse_lazy('projects:tasks') + f'?project={self.object.project.pk}'
    
    def delete(self, request, *args, **kwargs):
        task = self.get_object()
        messages.success(request, f'Ã„ÂÃƒÂ£ xÃƒÂ³a cÃƒÂ´ng viÃ¡Â»â€¡c "{task.name}".')
        return super().delete(request, *args, **kwargs)


class TaskUpdateStatusView(LoginRequiredMixin, View):
    """CÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t trÃ¡ÂºÂ¡ng thÃƒÂ¡i cÃƒÂ´ng viÃ¡Â»â€¡c (AJAX) - quÃ¡ÂºÂ£n lÃƒÂ½ vÃƒÂ  nhÃƒÂ¢n viÃƒÂªn Ã„â€˜Ã¡Â»Âu Ã„â€˜Ã†Â°Ã¡Â»Â£c phÃƒÂ©p."""
    def post(self, request, pk):
        from django.http import JsonResponse
        import json
        
        user = request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        # LÃ¡ÂºÂ¥y employee cÃ¡Â»Â§a user hiÃ¡Â»â€¡n tÃ¡ÂºÂ¡i (nÃ¡ÂºÂ¿u cÃƒÂ³)
        employee = None
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if is_manager:
            task = get_object_or_404(Task, pk=pk)
            if not DelayKPIService.can_approve_others(user):
                return JsonResponse({'success': False, 'error': 'KPI duoi nguong. Ban khong duoc phe duyet task cua nguoi khac.'}, status=403)
        else:
            # NhÃƒÂ¢n viÃƒÂªn chÃ¡Â»â€° cÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t tasks Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho mÃƒÂ¬nh hoÃ¡ÂºÂ·c tasks cÃ¡Â»Â§a projects do mÃƒÂ¬nh tÃ¡ÂºÂ¡o
            try:
                task = Task.objects.filter(
                    Q(assigned_to=employee) | Q(project__created_by=user)
                ).get(pk=pk)
            except Task.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'KhÃƒÂ´ng tÃƒÂ¬m thÃ¡ÂºÂ¥y cÃƒÂ´ng viÃ¡Â»â€¡c.'})
        
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in dict(Task.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'TrÃ¡ÂºÂ¡ng thÃƒÂ¡i khÃƒÂ´ng hÃ¡Â»Â£p lÃ¡Â»â€¡.'})
        
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
    """API endpoint Ã„â€˜Ã¡Â»Æ’ lÃ¡ÂºÂ¥y danh sÃƒÂ¡ch nhÃƒÂ¢n viÃƒÂªn theo phÃƒÂ²ng ban (AJAX)."""
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
    """CÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t trÃ¡ÂºÂ¡ng thÃƒÂ¡i giao/nhÃ¡ÂºÂ­n viÃ¡Â»â€¡c (AJAX)."""
    def post(self, request, pk):
        import json
        from django.utils import timezone
        user = request.user
        employee = None
        
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if not employee:
            return JsonResponse({'success': False, 'error': 'BÃ¡ÂºÂ¡n khÃƒÂ´ng phÃ¡ÂºÂ£i lÃƒÂ  nhÃƒÂ¢n viÃƒÂªn.'})
        
        # ChÃ¡Â»â€° cho phÃƒÂ©p nhÃƒÂ¢n viÃƒÂªn Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cÃƒÂ´ng viÃ¡Â»â€¡c cÃ¡ÂºÂ­p nhÃ¡ÂºÂ­t trÃ¡ÂºÂ¡ng thÃƒÂ¡i
        task = get_object_or_404(Task, pk=pk, assigned_to=employee)
        
        data = json.loads(request.body)
        new_status = data.get('assignment_status')
        
        if new_status not in dict(Task.ASSIGNMENT_STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'TrÃ¡ÂºÂ¡ng thÃƒÂ¡i khÃƒÂ´ng hÃ¡Â»Â£p lÃ¡Â»â€¡.'})
        
        task.assignment_status = new_status
        if new_status == 'in_progress' and task.started_at is None:
            task.started_at = timezone.now()
            task.status = 'in_progress'
        elif new_status == 'accepted' and task.status == 'done':
            task.status = 'todo'
        elif new_status == 'completed':
            task.status = 'done'
            if not task.completed_at:
                task.completed_at = timezone.now()
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
    """Trang xem cÃƒÂ´ng viÃ¡Â»â€¡c Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho user hiÃ¡Â»â€¡n tÃ¡ÂºÂ¡i."""
    model = Task
    template_name = 'projects/my_tasks.html'
    context_object_name = 'tasks'
    
    def get_queryset(self):
        user = self.request.user
        employee = None
        
        # LÃ¡ÂºÂ¥y employee cÃ¡Â»Â§a user hiÃ¡Â»â€¡n tÃ¡ÂºÂ¡i
        if hasattr(user, 'employee'):
            employee = user.employee
        
        if not employee:
            return Task.objects.none()
        
        # LÃ¡ÂºÂ¥y tÃ¡ÂºÂ¥t cÃ¡ÂºÂ£ tasks Ã„â€˜Ã†Â°Ã¡Â»Â£c gÃƒÂ¡n cho employee nÃƒÂ y
        queryset = Task.objects.filter(
            assigned_to=employee
        ).select_related('project', 'department').order_by('-due_date', '-created_at')
        
        # Filter theo trÃ¡ÂºÂ¡ng thÃƒÂ¡i nÃ¡ÂºÂ¿u cÃƒÂ³
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter theo trÃ¡ÂºÂ¡ng thÃƒÂ¡i giao/nhÃ¡ÂºÂ­n nÃ¡ÂºÂ¿u cÃƒÂ³
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



