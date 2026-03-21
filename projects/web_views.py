"""Web views for Projects Management."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from datetime import timedelta

from .models import Project, Task, TimeEntry, PersonnelRecommendation
from .forms import ProjectForm
from .personnel_forms import PersonnelRecommendationForm
from .personnel_services import PersonnelRecommendationService, BudgetMonitoringService
from resources.models import ResourceAllocation, Employee
from budgeting.models import Budget, Expense
from ai.services import AIService
from core.mixins import ManagerRequiredMixin
from core.notification_service import NotificationService
from core.models import Notification
from django.http import JsonResponse
from django.views import View


class ProjectListView(LoginRequiredMixin, ListView):
    """Danh sách dự án với filter và search."""
    model = Project
    template_name = 'projects/list.html'
    context_object_name = 'projects'
    paginate_by = 12

    def get_queryset(self):
        # Quản lý xem tất cả, nhân viên chỉ xem projects được phân bổ
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            # Quản lý xem tất cả projects
            queryset = Project.objects.select_related('client').annotate(
                task_count=Count('tasks'),
                completed_task_count=Count('tasks', filter=Q(tasks__status='done')),
                total_budget=Sum('budgets__allocated_amount'),
                total_spent=Sum('budgets__spent_amount'),
            )
        else:
            # Nhân viên chỉ xem projects được phân bổ vào (ResourceAllocation)
            employee = getattr(user, 'employee', None)
            if employee:
                # Lấy projects từ ResourceAllocation
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                queryset = Project.objects.filter(
                    id__in=allocated_project_ids
                ).select_related('client').annotate(
                    task_count=Count('tasks'),
                    completed_task_count=Count('tasks', filter=Q(tasks__status='done')),
                    total_budget=Sum('budgets__allocated_amount'),
                    total_spent=Sum('budgets__spent_amount'),
                )
            else:
                # Nếu không có employee record, trả về empty queryset
                queryset = Project.objects.none()

        # Filter theo status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter theo priority
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Search
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
        context['status_filter'] = self.request.GET.get('status', '')
        context['priority_filter'] = self.request.GET.get('priority', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Stats - quản lý xem tất cả, nhân viên chỉ projects được phân bổ
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            user_projects = Project.objects.all()
        else:
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                user_projects = Project.objects.filter(id__in=allocated_project_ids)
            else:
                user_projects = Project.objects.none()
        context['total_projects'] = user_projects.count()
        context['active_projects'] = user_projects.filter(status='active').count()
        context['completed_projects'] = user_projects.filter(status='completed').count()
        
        return context


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """Chi tiết dự án với tasks, budget, timeline."""
    model = Project
    template_name = 'projects/detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        """Quản lý xem tất cả, nhân viên chỉ xem projects được phân bổ."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Project.objects.all()
        else:
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                return Project.objects.filter(id__in=allocated_project_ids)
            else:
                return Project.objects.none()
        return Project.objects.filter(created_by=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()

        # Tasks
        context['tasks'] = project.tasks.select_related('assigned_to', 'phase').order_by('due_date', 'created_at')
        context['task_stats'] = {
            'total': project.tasks.count(),
            'todo': project.tasks.filter(status='todo').count(),
            'in_progress': project.tasks.filter(status='in_progress').count(),
            'review': project.tasks.filter(status='review').count(),
            'done': project.tasks.filter(status='done').count(),
        }

        # Phases with progress
        phases = project.phases.prefetch_related('tasks__assigned_to').all()
        phases_data = []
        for phase in phases:
            phase_tasks = phase.tasks.select_related('assigned_to').order_by('due_date', 'created_at')
            phases_data.append({
                'phase': phase,
                'tasks': phase_tasks,
                'progress': round(phase.calculated_progress, 0),
                'task_count': phase.task_count,
            })
        context['phases_data'] = phases_data
        context['unphased_tasks'] = project.tasks.filter(phase__isnull=True).select_related('assigned_to').order_by('due_date', 'created_at')

        # Project overall progress (average of all tasks' progress_percent)
        context['project_progress'] = round(project.calculated_progress, 0)

        # Budget
        budgets = project.budgets.all()
        context['budgets'] = budgets
        context['total_allocated'] = sum(b.allocated_amount for b in budgets)
        context['total_spent'] = sum(b.spent_amount for b in budgets)
        context['remaining_budget'] = context['total_allocated'] - context['total_spent']
        context['budget_utilization'] = (context['total_spent'] / context['total_allocated'] * 100) if context['total_allocated'] > 0 else 0

        # Resource allocations - tính từ tasks thay vì allocations
        # Lấy tất cả employees được gán công việc trong dự án (gộp trùng lặp)
        from django.db.models import Count, Sum, Q
        from resources.models import Employee
        
        # Sử dụng dictionary để gộp các employee trùng lặp
        employee_dict = {}
        
        # Lấy tất cả tasks có assigned_to
        tasks_with_employees = project.tasks.filter(assigned_to__isnull=False).select_related('assigned_to')
        
        for task in tasks_with_employees:
            employee = task.assigned_to
            employee_id = employee.id
            
            if employee_id not in employee_dict:
                # Đếm số công việc của employee trong dự án
                task_count = project.tasks.filter(assigned_to=employee).count()
                total_tasks = context['task_stats']['total']
                # Tính % phân bổ dựa trên số công việc
                allocation_percentage = (task_count / total_tasks * 100) if total_tasks > 0 else 0
                
                # Lấy allocation từ ResourceAllocation nếu có
                allocation = project.allocations.filter(employee=employee).first()
                
                employee_dict[employee_id] = {
                    'employee': employee,
                    'department': employee.department,
                    'allocation_percentage': round(allocation_percentage, 1),
                    'task_count': task_count,
                    'start_date': allocation.start_date if allocation else project.start_date,
                    'end_date': allocation.end_date if allocation else project.end_date,
                }
        
        # Chuyển dictionary thành list và sắp xếp theo allocation_percentage giảm dần
        employee_allocations = list(employee_dict.values())
        employee_allocations.sort(key=lambda x: x['allocation_percentage'], reverse=True)
        context['employee_allocations'] = employee_allocations

        # Time entries
        context['recent_time_entries'] = TimeEntry.objects.filter(
            task__project=project
        ).select_related('employee', 'task').order_by('-date')[:10]

        # Completion rate
        total_tasks = context['task_stats']['total']
        completed_tasks = context['task_stats']['done']
        context['completion_rate'] = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Timeline info
        if project.start_date and project.end_date:
            total_days = (project.end_date - project.start_date).days
            if total_days > 0:
                days_passed = (timezone.now().date() - project.start_date).days
                context['timeline_progress'] = min((days_passed / total_days * 100), 100)
            else:
                context['timeline_progress'] = 0
        else:
            context['timeline_progress'] = 0

        # Today for template
        context['today'] = timezone.now().date()

        # AI Insights
        context['ai_insight'] = None
        context['ai_insight_error'] = None
        try:
            ai_insight = AIService.recommend_project_staffing(project.id)
            # Kiểm tra xem có data không
            if ai_insight and isinstance(ai_insight, dict):
                if ai_insight.get('no_data'):
                    context['ai_insight_error'] = ai_insight.get('summary', 'Chưa có đủ dữ liệu để phân tích.')
                else:
                    ai_insight['title'] = f'AI Insights - {project.name}'
                    context['ai_insight'] = ai_insight
        except Exception as e:
            error_msg = str(e)
            # Xử lý lỗi AI tạm thời - kiểm tra nhiều pattern
            if any(keyword in error_msg for keyword in ['API key', 'API_KEY', 'expired', 'API_KEY_INVALID', 'invalid API key']):
                context['ai_insight_error'] = 'Chức năng AI hiện đang được refactor. Vui lòng thử lại sau khi hoàn tất cấu hình mới.'
            elif '400' in error_msg or 'Bad Request' in error_msg:
                context['ai_insight_error'] = 'Lỗi kết nối với dịch vụ AI tạm thời. Vui lòng thử lại sau.'
            else:
                # Giới hạn độ dài thông báo lỗi
                error_display = error_msg[:150] + '...' if len(error_msg) > 150 else error_msg
                context['ai_insight_error'] = f'Lỗi khi tạo phân tích AI: {error_display}'

        return context


class ProjectCreateView(ManagerRequiredMixin, CreateView):
    """Tạo dự án mới - chỉ quản lý mới có quyền."""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/form.html'
    success_url = reverse_lazy('projects:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # Lưu departments
        project = form.instance
        departments = form.cleaned_data.get('departments', [])
        project.departments.set(departments)
        
        # Tạo ResourceAllocation cho tất cả employees thuộc các departments đã chọn
        from resources.models import Employee, ResourceAllocation
        from django.utils import timezone
        
        employees_added = []
        for department in departments:
            employees = Employee.objects.filter(department=department, is_active=True)
            for employee in employees:
                # Kiểm tra xem đã có allocation chưa
                existing_allocation = ResourceAllocation.objects.filter(
                    employee=employee,
                    project=project
                ).first()
                
                if not existing_allocation:
                    # Tạo ResourceAllocation mới với allocation_percentage mặc định 50%
                    ResourceAllocation.objects.create(
                        employee=employee,
                        project=project,
                        allocation_percentage=50.0,
                        start_date=project.start_date or timezone.now().date(),
                        end_date=project.end_date,
                        created_by=self.request.user
                    )
                    employees_added.append(employee.full_name)

                    # Thông báo cho nhân viên
                    if getattr(employee, "user", None):
                        NotificationService.notify(
                            user=employee.user,
                            title=f"Bạn được thêm vào dự án: {project.name}",
                            message=f"Bạn vừa được thêm vào dự án \"{project.name}\".",
                            level=Notification.LEVEL_INFO,
                            url=f"/projects/{project.pk}/",
                            actor=self.request.user,
                        )
        
        if employees_added:
            messages.info(self.request, f'Đã gán {len(employees_added)} nhân sự từ {len(departments)} phòng ban vào dự án.')
        
        messages.success(self.request, f'Đã tạo dự án "{form.instance.name}" thành công.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Tạo dự án mới'
        context['submit_text'] = 'Tạo dự án'
        from resources.models import Department
        context['departments'] = Department.objects.all().order_by('name')
        context['selected_departments'] = []  # Không có departments nào được chọn khi tạo mới
        context['selected_required_departments'] = []  # Không có required_departments nào được chọn khi tạo mới
        return context


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """Cập nhật dự án."""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/form.html'
    success_url = reverse_lazy('projects:list')

    def get_queryset(self):
        """Quản lý có thể sửa tất cả, nhân viên chỉ sửa của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Project.objects.all()
        return Project.objects.filter(created_by=user)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        
        # Cập nhật departments
        project = form.instance
        departments = form.cleaned_data.get('departments', [])
        project.departments.set(departments)
        
        # Cập nhật ResourceAllocation cho employees thuộc các departments
        from resources.models import Employee, ResourceAllocation
        from django.utils import timezone
        
        # Lấy tất cả employees hiện tại trong project
        current_employees = set(project.allocations.values_list('employee_id', flat=True))
        
        # Lấy tất cả employees từ departments mới
        new_employees = set()
        for department in departments:
            employees = Employee.objects.filter(department=department, is_active=True)
            new_employees.update(employees.values_list('id', flat=True))
        
        # Thêm employees mới
        employees_to_add = new_employees - current_employees
        employees_added = []
        for employee_id in employees_to_add:
            employee = Employee.objects.get(id=employee_id)
            existing_allocation = ResourceAllocation.objects.filter(
                employee=employee,
                project=project
            ).first()
            
            if not existing_allocation:
                ResourceAllocation.objects.create(
                    employee=employee,
                    project=project,
                    allocation_percentage=50.0,
                    start_date=project.start_date or timezone.now().date(),
                    end_date=project.end_date,
                    created_by=self.request.user
                )
                employees_added.append(employee.full_name)

                # Thông báo cho nhân viên
                if getattr(employee, "user", None):
                    NotificationService.notify(
                        user=employee.user,
                        title=f"Bạn được thêm vào dự án: {project.name}",
                        message=f"Bạn vừa được thêm vào dự án \"{project.name}\".",
                        level=Notification.LEVEL_INFO,
                        url=f"/projects/{project.pk}/",
                        actor=self.request.user,
                    )
        
        # Xóa allocations của employees không còn thuộc departments đã chọn
        employees_to_remove = current_employees - new_employees
        if employees_to_remove:
            ResourceAllocation.objects.filter(
                project=project,
                employee_id__in=employees_to_remove
            ).delete()
        
        if employees_added:
            messages.info(self.request, f'Đã cập nhật: thêm {len(employees_added)} nhân sự vào dự án.')
        
        messages.success(self.request, f'Đã cập nhật dự án "{form.instance.name}" thành công.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Chỉnh sửa: {self.get_object().name}'
        context['submit_text'] = 'Cập nhật'
        from resources.models import Department
        context['departments'] = Department.objects.all().order_by('name')
        # Lấy departments đã chọn
        project = self.get_object()
        context['selected_departments'] = list(project.departments.values_list('id', flat=True))
        context['selected_required_departments'] = list(project.required_departments.values_list('id', flat=True))
        return context


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """Xóa dự án."""
    model = Project
    template_name = 'projects/confirm_delete.html'
    success_url = reverse_lazy('projects:list')

    def get_queryset(self):
        """Quản lý có thể xóa tất cả, nhân viên chỉ xóa của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Project.objects.all()
        return Project.objects.filter(created_by=user)

    def delete(self, request, *args, **kwargs):
        from django.http import HttpResponseRedirect
        from urllib.parse import quote
        
        project = self.get_object()
        project_name = project.name
        messages.success(request, f'Đã xóa dự án "{project_name}".')
        result = super().delete(request, *args, **kwargs)
        
        # Redirect với parameter để hiển thị modal thông báo thành công
        return HttpResponseRedirect(reverse_lazy('projects:list') + f'?deleted={quote(project_name)}')


class PersonnelRecommendationView(ManagerRequiredMixin, View):
    """View để đề xuất nhân sự cho dự án."""
    
    def get(self, request, project_id):
        """Hiển thị form đề xuất nhân sự."""
        project = get_object_or_404(Project, pk=project_id)
        form = PersonnelRecommendationForm()
        
        # Lấy lịch sử đề xuất
        recommendations = PersonnelRecommendation.objects.filter(
            project=project
        ).order_by('-created_at')[:10]
        
        # Kiểm tra cảnh báo ngân sách
        budget_warning = BudgetMonitoringService.check_budget_warning(project)
        
        context = {
            'project': project,
            'form': form,
            'recommendations': recommendations,
            'budget_warning': budget_warning,
        }
        
        from django.shortcuts import render
        return render(request, 'projects/personnel_recommendation.html', context)
    
    def post(self, request, project_id):
        """Xử lý đề xuất nhân sự."""
        project = get_object_or_404(Project, pk=project_id)
        form = PersonnelRecommendationForm(request.POST)
        
        if form.is_valid():
            optimization_goal = form.cleaned_data['optimization_goal']
            use_ai = form.cleaned_data.get('use_ai', True)
            
            # Gọi service để đề xuất
            try:
                result = PersonnelRecommendationService.recommend_personnel(
                    project,
                    optimization_goal,
                    use_ai
                )
                
                if result and result.get('recommendations'):
                    # Lưu đề xuất
                    recommendation = PersonnelRecommendationService.save_recommendation(
                        project,
                        optimization_goal,
                        result,
                        request.user
                    )
                    
                    messages.success(
                        request,
                        f'Đã tạo đề xuất nhân sự thành công ({result["method"]}).'
                    )
                    
                    # Giữ nguyên ở trang đề xuất để xem kết quả
                    recommendations = PersonnelRecommendation.objects.filter(
                        project=project
                    ).order_by('-created_at')[:10]
                    budget_warning = BudgetMonitoringService.check_budget_warning(project)
                    
                    context = {
                        'project': project,
                        'form': PersonnelRecommendationForm(),  # Reset form
                        'recommendations': recommendations,
                        'budget_warning': budget_warning,
                        'new_recommendation': recommendation,  # Thêm recommendation mới vào context
                    }
                    
                    from django.shortcuts import render
                    return render(request, 'projects/personnel_recommendation.html', context)
                else:
                    messages.error(request, 'Không thể tạo đề xuất. Vui lòng thử lại.')
            except Exception as e:
                messages.error(request, f'Lỗi khi tạo đề xuất: {str(e)}')
        else:
            messages.error(request, 'Dữ liệu không hợp lệ.')
        
        # Nếu có lỗi, quay lại form
        recommendations = PersonnelRecommendation.objects.filter(
            project=project
        ).order_by('-created_at')[:10]
        budget_warning = BudgetMonitoringService.check_budget_warning(project)
        
        context = {
            'project': project,
            'form': form,
            'recommendations': recommendations,
            'budget_warning': budget_warning,
        }
        
        from django.shortcuts import render
        return render(request, 'projects/personnel_recommendation.html', context)


class PersonnelRecommendationDetailView(ManagerRequiredMixin, DetailView):
    """Xem chi tiết đề xuất nhân sự."""
    model = PersonnelRecommendation
    template_name = 'projects/personnel_recommendation_detail.html'
    context_object_name = 'recommendation'
    
    def get_queryset(self):
        return PersonnelRecommendation.objects.select_related(
            'project', 'created_by'
        ).prefetch_related(
            'personnelrecommendationdetail_set__employee'
        )


class ApplyPersonnelRecommendationView(ManagerRequiredMixin, View):
    """Áp dụng đề xuất nhân sự vào dự án."""
    
    def post(self, request, recommendation_id):
        """Áp dụng đề xuất bằng cách tạo ResourceAllocation."""
        recommendation = get_object_or_404(PersonnelRecommendation, pk=recommendation_id)
        project = recommendation.project
        
        # Lấy chi tiết đề xuất
        details = recommendation.personnelrecommendationdetail_set.all()
        
        created_count = 0
        updated_count = 0
        start_date = project.start_date or timezone.now().date()
        end_date = project.end_date
        
        for detail in details:
            # Tạo hoặc cập nhật ResourceAllocation
            allocation, created = ResourceAllocation.objects.get_or_create(
                employee=detail.employee,
                project=project,
                start_date=start_date,
                defaults={
                    'allocation_percentage': detail.allocation_percentage,
                    'end_date': end_date,
                    'notes': f'Áp dụng từ đề xuất nhân sự (ID: {recommendation.pk}): {detail.reasoning[:100] if detail.reasoning else "Không có lý do"}',
                    'created_by': request.user,
                }
            )
            
            if created:
                created_count += 1
                # Thông báo cho nhân viên
                if getattr(detail.employee, "user", None):
                    NotificationService.notify(
                        user=detail.employee.user,
                        title=f"Bạn được thêm vào dự án: {project.name}",
                        message=f"Bạn vừa được phân bổ vào dự án \"{project.name}\" (theo đề xuất nhân sự).",
                        level=Notification.LEVEL_INFO,
                        url=f"/projects/{project.pk}/",
                        actor=request.user,
                    )
            else:
                # Cập nhật nếu đã tồn tại
                allocation.allocation_percentage = detail.allocation_percentage
                allocation.end_date = end_date
                allocation.notes = f'Cập nhật từ đề xuất nhân sự (ID: {recommendation.pk}): {detail.reasoning[:100] if detail.reasoning else "Không có lý do"}'
                allocation.updated_by = request.user
                allocation.save()
                updated_count += 1
        
        # Đánh dấu đề xuất đã được áp dụng
        recommendation.is_applied = True
        recommendation.applied_at = timezone.now()
        recommendation.updated_by = request.user
        recommendation.save()
        
        if created_count > 0 or updated_count > 0:
            action_msg = []
            if created_count > 0:
                action_msg.append(f'Tạo {created_count} phân bổ mới')
            if updated_count > 0:
                action_msg.append(f'Cập nhật {updated_count} phân bổ')
            messages.success(
                request,
                f'Đã áp dụng đề xuất nhân sự thành công. {", ".join(action_msg)}.'
            )
        else:
            messages.info(request, 'Đề xuất đã được đánh dấu là đã áp dụng.')
        
        from django.shortcuts import redirect
        return redirect('projects:recommend_personnel', project_id=project.pk)


class BudgetMonitoringView(ManagerRequiredMixin, View):
    """API view để kiểm tra ngân sách."""
    
    def get(self, request, project_id):
        """Trả về thông tin ngân sách dạng JSON."""
        project = get_object_or_404(Project, pk=project_id)
        
        budget_info = BudgetMonitoringService.calculate_personnel_budget_usage(project)
        budget_warning = BudgetMonitoringService.check_budget_warning(project)
        
        return JsonResponse({
            'allocated_budget': float(budget_info['allocated_budget']),
            'used_budget': float(budget_info['used_budget']),
            'remaining_budget': float(budget_info['remaining_budget']),
            'usage_percentage': budget_info['usage_percentage'],
            'is_over_budget': budget_info['is_over_budget'],
            'has_warning': budget_warning['has_warning'],
            'warning_message': budget_warning['message'],
            'warning_severity': budget_warning['severity'],
        })
