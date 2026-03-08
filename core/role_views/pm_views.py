from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class PMDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_PROJECT'
    template_name = 'modules/pm/pages/dashboard.html'
