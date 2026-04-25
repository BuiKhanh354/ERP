"""Views for Phase Management, Gantt Chart data, and Task Progress updates."""
import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, UpdateView, DeleteView

from .models import Project, ProjectPhase, Task, TaskProgressLog
from .forms import PhaseForm
from core.mixins import ManagerRequiredMixin
from .delay_kpi_service import DelayKPIService
from .task_history_service import TaskHistoryService
from core.rbac import get_user_role_names


def user_can_approve_tasks(user):
    role_names = get_user_role_names(user)
    if role_names.intersection({'ADMIN', 'MANAGER'}):
        return True
    return False


# ============================================================
# Phase CRUD Views
# ============================================================

class PhaseCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Tạo giai đoạn mới cho dự án."""
    model = ProjectPhase
    form_class = PhaseForm
    template_name = 'projects/phase_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, pk=kwargs['project_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.project
        return kwargs

    def form_valid(self, form):
        phase = form.save(commit=False)
        phase.project = self.project
        # Auto set order_index to last position
        max_order = self.project.phases.aggregate(
            max_order=models.Max('order_index')
        )['max_order'] or 0
        phase.order_index = max_order + 1
        phase.created_by = self.request.user
        phase.save()
        messages.success(self.request, f'Đã tạo giai đoạn "{phase.phase_name}" thành công.')
        return redirect(reverse('projects:detail', kwargs={'pk': self.project.pk}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        context['title'] = 'Thêm giai đoạn'
        return context


class PhaseUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Cập nhật giai đoạn dự án."""
    model = ProjectPhase
    form_class = PhaseForm
    template_name = 'projects/phase_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_object().project
        return kwargs

    def form_valid(self, form):
        phase = form.save(commit=False)
        phase.updated_by = self.request.user
        phase.save()
        messages.success(self.request, f'Đã cập nhật giai đoạn "{phase.phase_name}" thành công.')
        return redirect(reverse('projects:detail', kwargs={'pk': phase.project.pk}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.object.project
        context['title'] = 'Sửa giai đoạn'
        return context


class PhaseDeleteView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Xóa giai đoạn dự án (AJAX)."""

    def post(self, request, pk):
        phase = get_object_or_404(ProjectPhase, pk=pk)
        project_pk = phase.project.pk
        phase_name = phase.phase_name

        # Unlink tasks from this phase (don't delete tasks, just remove phase reference)
        phase.tasks.update(phase=None)
        phase.delete()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Đã xóa giai đoạn "{phase_name}".'})

        messages.success(request, f'Đã xóa giai đoạn "{phase_name}" thành công.')
        return redirect(reverse('projects:detail', kwargs={'pk': project_pk}))


# ============================================================
# Phase Reorder API (AJAX)
# ============================================================

class PhaseReorderAPIView(LoginRequiredMixin, View):
    """API endpoint để sắp xếp lại thứ tự giai đoạn (drag & drop)."""

    def post(self, request):
        try:
            data = json.loads(request.body)
            phase_ids = data.get('phase_ids', [])

            if not phase_ids:
                return JsonResponse({'success': False, 'error': 'Danh sách phase trống.'}, status=400)

            for index, phase_id in enumerate(phase_ids):
                ProjectPhase.objects.filter(pk=phase_id).update(order_index=index)

            return JsonResponse({'success': True, 'message': 'Đã cập nhật thứ tự giai đoạn.'})
        except (json.JSONDecodeError, Exception) as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ============================================================
# Gantt Chart Data API
# ============================================================

class GanttDataAPIView(LoginRequiredMixin, View):
    """API trả về dữ liệu Gantt Chart cho dự án (JSON)."""

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        today = timezone.now().date()

        gantt_tasks = []

        phases = project.phases.prefetch_related('tasks__assigned_to').all()

        for phase in phases:
            # Add phase as a group bar
            phase_start = phase.start_date or project.start_date or today
            phase_end = phase.end_date or project.end_date or today
            gantt_tasks.append({
                'id': f'phase-{phase.pk}',
                'name': phase.phase_name,
                'start': phase_start.isoformat(),
                'end': phase_end.isoformat(),
                'progress': round(phase.calculated_progress, 0),
                'custom_class': 'gantt-phase',
                'is_phase': True,
            })

            # Add tasks within this phase
            for task in phase.tasks.all():
                task_start = task.created_at.date() if task.created_at else today
                task_end = task.due_date or phase_end
                gantt_tasks.append({
                    'id': f'task-{task.pk}',
                    'name': task.name,
                    'start': task_start.isoformat(),
                    'end': task_end.isoformat(),
                    'progress': task.progress_percent,
                    'dependencies': f'phase-{phase.pk}',
                    'custom_class': f'gantt-task gantt-status-{task.status}',
                    'is_phase': False,
                    'assignee': task.assigned_to.full_name if task.assigned_to else '',
                    'status': task.get_status_display(),
                })

        # Tasks not assigned to any phase
        unphased_tasks = project.tasks.filter(phase__isnull=True).select_related('assigned_to')
        if unphased_tasks.exists():
            for task in unphased_tasks:
                task_start = task.created_at.date() if task.created_at else today
                task_end = task.due_date or (project.end_date or today)
                gantt_tasks.append({
                    'id': f'task-{task.pk}',
                    'name': task.name,
                    'start': task_start.isoformat(),
                    'end': task_end.isoformat(),
                    'progress': task.progress_percent,
                    'custom_class': f'gantt-task gantt-status-{task.status}',
                    'is_phase': False,
                    'assignee': task.assigned_to.full_name if task.assigned_to else '',
                    'status': task.get_status_display(),
                })

        return JsonResponse({'tasks': gantt_tasks, 'project_name': project.name})


# ============================================================
# Task Progress Update API (AJAX)
# ============================================================

class TaskProgressUpdateView(LoginRequiredMixin, View):
    """API cập nhật tiến độ task (progress %, status, ghi chú)."""

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        employee = getattr(request.user, "employee", None)
        is_assignee = bool(employee and task.assigned_to_id and task.assigned_to_id == employee.id)
        can_approve = user_can_approve_tasks(request.user)
        if employee and task.assigned_to_id and task.assigned_to_id != employee.id:
            if not DelayKPIService.can_approve_others(request.user):
                return JsonResponse({'success': False, 'error': 'KPI duoi nguong. Ban khong duoc phe duyet task cua nguoi khac.'}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            # Fallback to POST data
            data = request.POST

        progress = data.get('progress_percent')
        status = data.get('status')
        note = data.get('note', '')
        delay_explanation = data.get('delay_explanation', '')

        updated_fields = []

        if progress is not None:
            try:
                progress = int(progress)
                if 0 <= progress <= 100:
                    task.progress_percent = progress
                    updated_fields.append('progress_percent')

                    # Auto-update status based on progress
                    if progress == 100 and task.status != 'done':
                        # Employee submit completion for review, manager does final approval.
                        task.status = 'review' if is_assignee and not can_approve else 'done'
                        updated_fields.append('status')
                    elif progress > 0 and task.status == 'todo':
                        task.status = 'in_progress'
                        updated_fields.append('status')
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Giá trị tiến độ không hợp lệ.'}, status=400)

        if status and status in dict(Task.STATUS_CHOICES):
            if status == 'done' and not can_approve:
                return JsonResponse({'success': False, 'error': 'Bạn không có quyền duyệt hoàn thành task.'}, status=403)
            if status == 'done' and task.status != 'review':
                return JsonResponse({'success': False, 'error': 'Task chỉ được chuyển Done sau bước Review.'}, status=400)
            task.status = status
            if 'status' not in updated_fields:
                updated_fields.append('status')

            # Auto-update progress based on status
            if status == 'done' and task.progress_percent < 100:
                task.progress_percent = 100
                if 'progress_percent' not in updated_fields:
                    updated_fields.append('progress_percent')
            if status == 'done' and not task.completed_at:
                task.completed_at = timezone.now()
                if 'completed_at' not in updated_fields:
                    updated_fields.append('completed_at')

        if delay_explanation:
            task.delay_explanation = str(delay_explanation).strip()

        config = DelayKPIService.get_active_config()
        due_days_late = 0
        if task.due_date:
            due_days_late = max((timezone.now().date() - task.due_date).days, 0)
        if (status == 'done' or task.status == 'done') and due_days_late > int(config.requires_explanation_after_days):
            if not (task.delay_explanation or note or '').strip():
                return JsonResponse({'success': False, 'error': 'Task tre han qua nguong, vui long nhap giai trinh.'}, status=400)

        task.updated_by = request.user
        TaskHistoryService.update_task_snapshots(task)
        task.save()
        DelayKPIService.update_task_delay_metrics(task, actor=request.user)
        TaskHistoryService.log(task, actor=request.user, event_type='status_changed', note='Progress/Status updated from phase board')

        # Create progress log
        TaskProgressLog.objects.create(
            task=task,
            user=request.user,
            progress_percent=task.progress_percent,
            note=note,
            created_by=request.user,
        )

        return JsonResponse({
            'success': True,
            'message': 'Đã cập nhật tiến độ thành công.',
            'progress_percent': task.progress_percent,
            'status': task.status,
            'status_display': task.get_status_display(),
            'phase_progress': round(task.phase.calculated_progress, 0) if task.phase else None,
            'project_progress': round(task.project.calculated_progress, 0),
        })
