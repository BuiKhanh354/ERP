from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class ExecutiveDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_COMPANY_DASHBOARD'
    template_name = 'modules/executive/pages/dashboard.html'


class ExecutiveProjectPortfolioView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_PROJECTS'
    template_name = 'modules/executive/pages/project_portfolio.html'


class ExecutiveFinancialReportsView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_financial_report'
    template_name = 'modules/executive/pages/financial_reports.html'


class ExecutivePerformanceView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_performance'
    template_name = 'modules/executive/pages/performance.html'
