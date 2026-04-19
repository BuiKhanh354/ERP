from collections import defaultdict

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.rbac import PermissionRequiredMixin
from core.role_views.admin_views import AdminProjectMembersView, AdminAddProjectMemberView
from projects.models import Project, PersonnelRecommendation
from projects.personnel_forms import PersonnelRecommendationForm
from projects.personnel_services import PersonnelRecommendationService, BudgetMonitoringService
from resources.models import Department, Employee, ResourceAllocation

class ResourceDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        employees = list(Employee.objects.filter(is_active=True).select_related('department'))
        total_employees = len(employees)

        allocation_rows = (
            ResourceAllocation.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .order_by()
            .values('employee_id')
            .annotate(total_alloc=Sum('allocation_percentage'))
        )
        alloc_map = {row['employee_id']: float(row['total_alloc'] or 0) for row in allocation_rows}

        allocated_count = sum(1 for e in employees if alloc_map.get(e.id, 0) > 0)
        unallocated_count = max(0, total_employees - allocated_count)

        utilization_values = [alloc_map.get(e.id, 0.0) for e in employees]
        avg_utilization = round(sum(utilization_values) / total_employees, 2) if total_employees else 0
        over_utilized = [e for e in employees if alloc_map.get(e.id, 0) > 100]
        under_utilized = [e for e in employees if 0 < alloc_map.get(e.id, 0) < 50]

        # Projects needing resources: active projects with few/zero allocations
        needs_resource_count = 0
        for p in Project.objects.filter(status='active'):
            alloc_employee_cnt = ResourceAllocation.objects.filter(
                project=p
            ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).values('employee_id').distinct().count()
            if alloc_employee_cnt == 0 or alloc_employee_cnt < max(1, int(p.estimated_employees or 0) // 2):
                needs_resource_count += 1

        # Distribution bins
        bins = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0, '>100%': 0}
        for val in utilization_values:
            if val <= 25:
                bins['0-25%'] += 1
            elif val <= 50:
                bins['25-50%'] += 1
            elif val <= 75:
                bins['50-75%'] += 1
            elif val <= 100:
                bins['75-100%'] += 1
            else:
                bins['>100%'] += 1

        # Allocation by department
        dept_alloc = defaultdict(int)
        for e in employees:
            if alloc_map.get(e.id, 0) > 0:
                dept_name = e.department.name if e.department else 'Chưa phân phòng ban'
                dept_alloc[dept_name] += 1

        context.update(
            {
                'total_employees': total_employees,
                'allocated_count': allocated_count,
                'unallocated_count': unallocated_count,
                'avg_utilization': avg_utilization,
                'over_utilized_count': len(over_utilized),
                'needs_resource_count': needs_resource_count,
                'utilization_labels': list(bins.keys()),
                'utilization_data': list(bins.values()),
                'allocation_dept_labels': list(dept_alloc.keys()),
                'allocation_dept_data': list(dept_alloc.values()),
                'over_utilized_employees': [
                    {'name': e.full_name, 'department': e.department.name if e.department else '—', 'utilization': round(alloc_map.get(e.id, 0), 2)}
                    for e in over_utilized[:8]
                ],
                'under_utilized_employees': [
                    {'name': e.full_name, 'department': e.department.name if e.department else '—', 'utilization': round(alloc_map.get(e.id, 0), 2)}
                    for e in under_utilized[:8]
                ],
            }
        )
        return context


class ResourceAllocationListView(PermissionRequiredMixin, TemplateView):
    permission_required = 'RESOURCE_ALLOCATE'
    template_name = 'modules/resource_manager/pages/allocation_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = Project.objects.filter(status__in=['planning', 'active', 'on_hold']).order_by('name')
        employees = Employee.objects.filter(is_active=True).select_related('department').order_by('last_name', 'first_name')
        departments = Department.objects.filter(is_active=True).order_by('name')

        project_id = (self.request.GET.get('project') or '').strip()
        employee_id = (self.request.GET.get('employee') or '').strip()
        department_id = (self.request.GET.get('department') or '').strip()

        allocations = ResourceAllocation.objects.select_related(
            'employee__department',
            'project',
        ).order_by('-start_date', '-created_at')

        if project_id:
            allocations = allocations.filter(project_id=project_id)
        if employee_id:
            allocations = allocations.filter(employee_id=employee_id)
        if department_id:
            allocations = allocations.filter(employee__department_id=department_id)

        context['rm_projects'] = projects
        context['rm_employees'] = employees
        context['rm_departments'] = departments
        context['allocations'] = allocations
        context['default_project_id'] = projects.first().id if projects.exists() else None
        context['selected_project_id'] = project_id
        context['selected_employee_id'] = employee_id
        context['selected_department_id'] = department_id
        return context


class ResourceCapacityPlanningView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/capacity.html'


class ResourceProjectResourcesView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/project_resources.html'


class ResourceManagerProjectMembersView(AdminProjectMembersView):
    permission_required = 'RESOURCE_ALLOCATE'
    template_name = 'modules/resource_manager/pages/project_members.html'


class ResourceManagerAddProjectMemberView(AdminAddProjectMemberView):
    permission_required = 'RESOURCE_ALLOCATE'
    template_name = 'modules/resource_manager/pages/add_project_member.html'


class ResourceManagerPersonnelRecommendationView(PermissionRequiredMixin, View):
    permission_required = 'RESOURCE_ALLOCATE'

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        form = PersonnelRecommendationForm()
        recommendations = PersonnelRecommendation.objects.filter(project=project).order_by('-created_at')[:10]
        budget_warning = BudgetMonitoringService.check_budget_warning(project)
        context = {
            'project': project,
            'form': form,
            'recommendations': recommendations,
            'budget_warning': budget_warning,
        }
        return render(request, 'modules/resource_manager/pages/personnel_recommendation.html', context)

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        form = PersonnelRecommendationForm(request.POST)
        if form.is_valid():
            optimization_goal = form.cleaned_data['optimization_goal']
            use_ai = form.cleaned_data.get('use_ai', True)
            try:
                result = PersonnelRecommendationService.recommend_personnel(
                    project,
                    optimization_goal,
                    use_ai
                )
                if result and result.get('recommendations'):
                    recommendation = PersonnelRecommendationService.save_recommendation(
                        project,
                        optimization_goal,
                        result,
                        request.user
                    )
                    from django.contrib import messages
                    messages.success(request, f'Da tao de xuat nhan su thanh cong ({result["method"]}).')
                    recommendations = PersonnelRecommendation.objects.filter(project=project).order_by('-created_at')[:10]
                    budget_warning = BudgetMonitoringService.check_budget_warning(project)
                    context = {
                        'project': project,
                        'form': PersonnelRecommendationForm(),
                        'recommendations': recommendations,
                        'budget_warning': budget_warning,
                        'new_recommendation': recommendation,
                    }
                    return render(request, 'modules/resource_manager/pages/personnel_recommendation.html', context)
                else:
                    from django.contrib import messages
                    failure_reason = str((result or {}).get('reasoning', '')).strip()
                    messages.error(request, failure_reason or 'Khong the tao de xuat. Vui long thu lai.')
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Loi khi tao de xuat: {str(e)}')
        else:
            from django.contrib import messages
            messages.error(request, 'Du lieu khong hop le.')

        recommendations = PersonnelRecommendation.objects.filter(project=project).order_by('-created_at')[:10]
        budget_warning = BudgetMonitoringService.check_budget_warning(project)
        context = {
            'project': project,
            'form': form,
            'recommendations': recommendations,
            'budget_warning': budget_warning,
        }
        return render(request, 'modules/resource_manager/pages/personnel_recommendation.html', context)


class ResourceManagerRecommendationDetailView(PermissionRequiredMixin, TemplateView):
    permission_required = 'RESOURCE_ALLOCATE'
    template_name = 'projects/personnel_recommendation_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recommendation = get_object_or_404(
            PersonnelRecommendation.objects.select_related('project', 'created_by').prefetch_related(
                'personnelrecommendationdetail_set__employee'
            ),
            pk=self.kwargs.get('pk')
        )
        context['recommendation'] = recommendation
        return context


class ResourceManagerApplyRecommendationView(PermissionRequiredMixin, View):
    permission_required = 'RESOURCE_ALLOCATE'

    def post(self, request, recommendation_id):
        from projects.web_views import ApplyPersonnelRecommendationView
        # Reuse existing apply logic and then redirect back RM page.
        response = ApplyPersonnelRecommendationView().post(request, recommendation_id=recommendation_id)
        recommendation = get_object_or_404(PersonnelRecommendation, pk=recommendation_id)
        return redirect('resource_manager_module:recommend_personnel', project_id=recommendation.project_id)
