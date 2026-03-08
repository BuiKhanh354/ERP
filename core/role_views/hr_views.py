from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class HRDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_EMPLOYEE_PROFILE'
    template_name = 'modules/hr/pages/dashboard.html'
