from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class ResourceDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/dashboard.html'


class ResourceAllocationListView(PermissionRequiredMixin, TemplateView):
    permission_required = 'RESOURCE_ALLOCATE'
    template_name = 'modules/resource_manager/pages/allocation_list.html'


class ResourceCapacityPlanningView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/capacity.html'


class ResourceProjectResourcesView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_RESOURCES'
    template_name = 'modules/resource_manager/pages/project_resources.html'
