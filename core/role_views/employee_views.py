from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class EmployeeDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'modules/employee/pages/dashboard.html'
