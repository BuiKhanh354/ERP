"""Web views for Task Management (Checklist)."""
import json
import pickle
from functools import lru_cache
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse

from ai.audit import log_ai_usage, start_timer
from .models import Task, Project, ProjectPhase
from .forms import TaskForm
from resources.models import Employee, Department
from core.mixins import ManagerRequiredMixin
from django.utils import timezone
from core.notification_service import NotificationService
from core.models import Notification
from .delay_kpi_service import DelayKPIService
from .task_history_service import TaskHistoryService
from core.rbac import get_user_role_names, get_client_ip

BASE_DIR = Path(__file__).resolve().parent.parent
TASK_RISK_MODEL_PATH = BASE_DIR / "ai" / "models" / "task_risk_xgb.pkl"
TASK_RISK_SHAP_TOP_PATH = BASE_DIR / "ai" / "models" / "task_risk_shap_top_features.json"


def _get_form_assignees(form):
    assignees = list(form.cleaned_data.get('assignees') or [])
    if assignees:
        return assignees
    assigned_to = form.cleaned_data.get('assigned_to')
    return [assigned_to] if assigned_to else []


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


def build_task_risk_assessment(task):
    """Rule-based risk scoring for task delay (minimal AI, no training)."""
    score = 0
    reasons = []
    suggestions = []

    today = timezone.localdate()
    days_to_due = None
    if task.due_date:
        days_to_due = (task.due_date - today).days

    progress = int(task.progress_percent or 0)

    if task.status == 'overdue':
        score += 45
        reasons.append('Task da o trang thai qua han.')
        suggestions.append('Can uu tien xu ly task nay trong ngay.')

    if days_to_due is not None:
        if days_to_due < 0 and progress < 100:
            score += 30
            reasons.append(f'Da tre han {abs(days_to_due)} ngay nhung chua hoan thanh.')
            suggestions.append('Can chot lai deadline moi va cap nhat ly do tre han.')
        elif days_to_due <= 2 and progress < 70:
            score += 25
            reasons.append('Sap toi han (<=2 ngay) nhung tien do duoi 70%.')
            suggestions.append('Chia nho task va kiem tra tien do hang ngay.')
        elif days_to_due <= 5 and progress < 50:
            score += 15
            reasons.append('Con <=5 ngay nhung tien do duoi 50%.')
            suggestions.append('Can bo sung nguon luc hoac giam scope trong phase hien tai.')

    estimated_hours = float(task.estimated_hours or 0)
    actual_hours = float(task.actual_hours or 0)
    if estimated_hours > 0 and actual_hours > estimated_hours * 1.2:
        score += 10
        reasons.append('Gio thuc te da vuot 120% gio uoc tinh.')
        suggestions.append('Can review lai effort estimate cho cac task tuong tu.')

    assignee = getattr(task, 'assigned_to', None)
    if assignee:
        if int(assignee.warning_count or 0) >= 3:
            score += 10
            reasons.append('Nhan su co warning tre han cao (>=3).')
            suggestions.append('Manager nen theo doi sat va dat moc trung gian ro rang.')
        if float(assignee.kpi_current or 0) < 70:
            score += 8
            reasons.append('KPI hien tai cua nhan su duoi 70.')
            suggestions.append('Can coaching ngan va xac nhan lai uu tien cong viec.')

    score = max(0, min(100, score))
    if score >= 65:
        risk_level = 'high'
    elif score >= 35:
        risk_level = 'medium'
    else:
        risk_level = 'low'

    if not reasons:
        reasons = ['Khong co dau hieu rui ro lon o thoi diem hien tai.']
    if not suggestions:
        suggestions = ['Tiep tuc cap nhat tien do deu va giu deadline hien tai.']

    recommendation = _build_personalized_recommendation(
        task=task,
        risk_level=risk_level,
        score=score,
        days_to_due=days_to_due,
        reasons=reasons[:3],
        suggestions=suggestions[:2],
    )
    return {
        'risk_score': score,
        'risk_level': risk_level,
        'days_to_due': days_to_due,
        'reasons': reasons[:3],
        'suggestions': suggestions[:2],
        'recommendation': recommendation,
    }


@lru_cache(maxsize=1)
def _load_task_risk_model():
    if not TASK_RISK_MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {TASK_RISK_MODEL_PATH}")
    with open(TASK_RISK_MODEL_PATH, "rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=1)
def _load_shap_top_features():
    if not TASK_RISK_SHAP_TOP_PATH.exists():
        return []
    try:
        payload = json.loads(TASK_RISK_SHAP_TOP_PATH.read_text(encoding="utf-8"))
        return payload.get("top_features", [])
    except Exception:
        return []


def _extract_ml_features(task):
    today = timezone.localdate()
    days_to_due = (task.due_date - today).days if task.due_date else 999
    assignee = getattr(task, 'assigned_to', None)
    warning_count = int(getattr(assignee, 'warning_count', 0) or 0)
    kpi_current = float(getattr(assignee, 'kpi_current', 100) or 100)
    has_overdue_history = 1 if warning_count > 0 else 0
    is_critical = 1 if task.priority == 'critical' else 0

    features = {
        "progress_percent": float(task.progress_percent or 0),
        "days_to_due": float(days_to_due),
        "estimated_hours": float(task.estimated_hours or 0),
        "actual_hours": float(task.actual_hours or 0),
        "warning_count": float(warning_count),
        "kpi_current": float(kpi_current),
        "has_overdue_history": float(has_overdue_history),
        "is_critical": float(is_critical),
    }
    return features


def _build_ml_reasons_and_suggestions(features, risk_level):
    reasons = []
    suggestions = []

    if features["days_to_due"] < 0:
        reasons.append(f"Da tre han {abs(int(features['days_to_due']))} ngay.")
    elif features["days_to_due"] <= 2:
        reasons.append("Con it ngay den deadline.")

    if features["progress_percent"] < 60:
        reasons.append("Tien do hien tai duoi 60%.")
    if features["estimated_hours"] > 0 and features["actual_hours"] > features["estimated_hours"] * 1.2:
        reasons.append("Gio thuc te cao hon uoc tinh >20%.")
    if features["warning_count"] >= 3:
        reasons.append("Nhan su co warning tre han cao.")
    if features["kpi_current"] < 70:
        reasons.append("KPI nhan su dang duoi 70.")

    if risk_level == "high":
        suggestions.append("Dat moc check-in hang ngay va uu tien task nay.")
        suggestions.append("Can nhac dieu chinh deadline/scope va ghi ro ly do.")
    elif risk_level == "medium":
        suggestions.append("Chia nho task thanh cac moc ngan de theo doi.")
        suggestions.append("Review effort estimate voi manager trong ngay.")
    else:
        suggestions.append("Tiep tuc tien do hien tai va cap nhat trang thai deu.")

    # If SHAP top features exist, ưu tiên mention 1-2 feature đầu cho báo cáo.
    top_features = _load_shap_top_features()
    if top_features:
        top_names = [f.get("feature") for f in top_features[:2] if isinstance(f, dict)]
        if top_names:
            reasons.append(f"Model uu tien dac trung: {', '.join(top_names)}.")

    if not reasons:
        reasons = ["Khong co dau hieu rui ro lon o thoi diem hien tai."]
    return reasons[:3], suggestions[:2]


def _build_personalized_recommendation(task, risk_level, score, days_to_due, reasons, suggestions):
    assignee = getattr(task, 'assigned_to', None)
    warning_count = int(getattr(assignee, 'warning_count', 0) or 0) if assignee else 0
    kpi_current = float(getattr(assignee, 'kpi_current', 100) or 100) if assignee else 100.0
    estimated_hours = float(task.estimated_hours or 0)
    actual_hours = float(task.actual_hours or 0)

    actions = []
    if days_to_due is not None:
        if days_to_due < 0:
            actions.append(f"task da tre han {abs(int(days_to_due))} ngay, can chot lai deadline moi trong hom nay")
        elif days_to_due <= 2:
            actions.append("deadline rat gan, can check-in 2 lan/ngay cho den khi on dinh tien do")
        elif days_to_due <= 5:
            actions.append("deadline can ke, nen tach nho cong viec theo moc ngay")

    if estimated_hours > 0 and actual_hours > estimated_hours * 1.2:
        actions.append("gio thuc te dang vuot estimate, can review lai effort va giam bot scope phu")

    if warning_count >= 3:
        actions.append("nhan su co warning cao, manager nen theo doi sat va xac nhan ket qua cuoi ngay")
    elif kpi_current < 70:
        actions.append("KPI nhan su thap, nen uu tien mentoring ngan va lam ro uu tien cong viec")

    if not actions and suggestions:
        actions.extend(suggestions[:2])
    if not actions:
        actions.append("duy tri tien do hien tai va cap nhat trang thai deu hang ngay")

    if risk_level == "high":
        prefix = f"Rui ro cao ({score}%)."
    elif risk_level == "medium":
        prefix = f"Rui ro trung binh ({score}%)."
    else:
        prefix = f"Rui ro thap ({score}%)."

    reason_hint = reasons[0] if reasons else "Chua phat hien dau hieu bat thuong."
    return f"{prefix} Nguyen nhan chinh: {reason_hint} De xuat: {actions[0]}."


def build_task_risk_assessment_ml_or_fallback(task):
    """Try ML prediction first; fallback to rule-based on any error."""
    today = timezone.localdate()
    days_to_due = (task.due_date - today).days if task.due_date else None
    try:
        model = _load_task_risk_model()
        features = _extract_ml_features(task)
        ordered = [[
            features["progress_percent"],
            features["days_to_due"],
            features["estimated_hours"],
            features["actual_hours"],
            features["warning_count"],
            features["kpi_current"],
            features["has_overdue_history"],
            features["is_critical"],
        ]]
        probability = float(model.predict_proba(ordered)[0][1])
        score = int(round(probability * 100))
        if score >= 65:
            risk_level = "high"
        elif score >= 35:
            risk_level = "medium"
        else:
            risk_level = "low"
        reasons, suggestions = _build_ml_reasons_and_suggestions(features, risk_level)
        recommendation = _build_personalized_recommendation(
            task=task,
            risk_level=risk_level,
            score=score,
            days_to_due=days_to_due,
            reasons=reasons,
            suggestions=suggestions,
        )
        return {
            "risk_score": score,
            "risk_level": risk_level,
            "days_to_due": days_to_due,
            "reasons": reasons,
            "suggestions": suggestions,
            "recommendation": recommendation,
            "engine": "ml",
            "fallback_used": False,
        }
    except Exception as exc:
        result = build_task_risk_assessment(task)
        result["engine"] = "rule-based"
        result["fallback_used"] = True
        result["fallback_reason"] = str(exc)
        return result


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
                            Q(assigned_to=employee) | Q(assignees=employee) | Q(project__created_by=user)
                        )
                    ).distinct()
                # Auto mark overdue: đã quá due_date hoặc quá estimated_end_at
                candidates = qs.filter(status__in=['todo', 'in_progress', 'review', 'overdue']).select_related('project', 'assigned_to')
                DelayKPIService.sync_overdue_tasks(candidates, actor=user)
                return qs.select_related('project', 'assigned_to', 'department').prefetch_related('assignees').order_by('status', 'due_date', 'created_at')
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
        selected_assignees = _get_form_assignees(form)
        if form.instance.priority == 'critical':
            low_kpi_assignees = [emp.full_name for emp in selected_assignees if float(emp.kpi_current or 0) < 70]
            if low_kpi_assignees:
                form.add_error('assignees', f"Nhan su duoc giao task critical phai co KPI >= 70. Vi pham: {', '.join(low_kpi_assignees)}")
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
            assignees = list(task.assignees.select_related("user").all())
            if not assignees and getattr(task, "assigned_to", None):
                assignees = [task.assigned_to]
            for assigned_emp in assignees:
                assigned_user = getattr(assigned_emp, "user", None)
                if not assigned_user:
                    continue
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
                return Task.objects.filter(Q(assigned_to=employee) | Q(assignees=employee)).distinct()
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
        old_assignee_ids = set(old_task.assignees.values_list('id', flat=True))
        if not old_assignee_ids and old_task.assigned_to_id:
            old_assignee_ids = {old_task.assigned_to_id}

        if form.instance.priority == 'critical' and not DelayKPIService.can_assign_critical_task(user):
            form.add_error(None, 'KPI hien tai duoi nguong 70, ban khong duoc phep giao task quan trong.')
            return self.form_invalid(form)
        selected_assignees = _get_form_assignees(form)
        if form.instance.priority == 'critical':
            low_kpi_assignees = [emp.full_name for emp in selected_assignees if float(emp.kpi_current or 0) < 70]
            if low_kpi_assignees:
                form.add_error('assignees', f"Nhan su duoc giao task critical phai co KPI >= 70. Vi pham: {', '.join(low_kpi_assignees)}")
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
                new_assignee_ids = set(task.assignees.values_list('id', flat=True))
                if not new_assignee_ids and task.assigned_to_id:
                    new_assignee_ids = {task.assigned_to_id}
                added_assignee_ids = new_assignee_ids - old_assignee_ids
                if added_assignee_ids:
                    TaskHistoryService.log(task, actor=user, event_type='assigned', note='Assignee changed')
                    for assigned_emp in Employee.objects.filter(id__in=added_assignee_ids).select_related("user"):
                        assigned_user = getattr(assigned_emp, "user", None)
                        if not assigned_user:
                            continue
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
                    Q(assigned_to=employee) | Q(assignees=employee) | Q(project__created_by=user)
                ).distinct().get(pk=pk)
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
        task = get_object_or_404(
            Task.objects.filter(Q(assigned_to=employee) | Q(assignees=employee)).distinct(),
            pk=pk
        )
        
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
            Q(assigned_to=employee) | Q(assignees=employee)
        ).distinct().select_related('project', 'department').prefetch_related('assignees').order_by('-due_date', '-created_at')
        
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


class TaskRiskAssessmentAPIView(LoginRequiredMixin, View):
    """AI endpoint: ML first, fallback to rule-based if ML fails."""

    def get(self, request, pk):
        started = start_timer()
        user = request.user
        is_manager = user_has_manager_capability(user)

        if is_manager:
            task = get_object_or_404(Task.objects.select_related('assigned_to'), pk=pk)
        else:
            employee = getattr(user, 'employee', None)
            if not employee:
                log_ai_usage(
                    user=user,
                    endpoint=f"/projects/api/tasks/{pk}/risk-assessment/",
                    request_payload={"task_id": pk},
                    response_payload={"error": "employee_profile_missing"},
                    status_code=403,
                    source="rbac",
                    ip_address=get_client_ip(request),
                    started_at=started,
                )
                return JsonResponse({'ok': False, 'error': 'Ban khong co ho so nhan su.'}, status=403)
            task = get_object_or_404(
                Task.objects.filter(Q(assigned_to=employee) | Q(assignees=employee)).select_related('assigned_to').distinct(),
                pk=pk,
            )

        assessment = build_task_risk_assessment_ml_or_fallback(task)
        log_ai_usage(
            user=user,
            endpoint=f"/projects/api/tasks/{pk}/risk-assessment/",
            request_payload={"task_id": task.pk},
            response_payload={
                "risk_level": assessment.get("risk_level"),
                "risk_score": assessment.get("risk_score"),
                "engine": assessment.get("engine"),
            },
            status_code=200,
            source=assessment.get("engine", "rule-based"),
            fallback_used=bool(assessment.get("fallback_used", False)),
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return JsonResponse({
            'ok': True,
            'task_id': task.pk,
            'task_name': task.name,
            **assessment,
        })
