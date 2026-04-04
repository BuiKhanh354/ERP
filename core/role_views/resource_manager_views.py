from collections import defaultdict

from django.db.models import Q, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from core.rbac import PermissionRequiredMixin
from projects.models import Project
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


class ResourceCapacityPlanningView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/capacity.html'


class ResourceProjectResourcesView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/project_resources.html'
