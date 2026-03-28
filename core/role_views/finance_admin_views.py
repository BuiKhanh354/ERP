from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin

class FinanceAdminDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_PROJECT_FINANCE'
    template_name = 'modules/finance_admin/pages/dashboard.html'


class BudgetApprovalView(PermissionRequiredMixin, TemplateView):
    permission_required = 'APPROVE_BUDGET'
    template_name = 'modules/finance_admin/pages/budget_approval.html'


class ExpenseApprovalView(PermissionRequiredMixin, TemplateView):
    permission_required = 'approve_expense'
    template_name = 'modules/finance_admin/pages/expense_approval.html'


class FinancialPeriodView(PermissionRequiredMixin, TemplateView):
    permission_required = 'LOCK_FINANCIAL_PERIOD'
    template_name = 'modules/finance_admin/pages/financial_periods.html'


class ActualCostView(PermissionRequiredMixin, TemplateView):
    permission_required = 'EDIT_ACTUAL_COST'
    template_name = 'modules/finance_admin/pages/actual_costs.html'


class FinancialReportsView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_financial_report'
    template_name = 'modules/finance_admin/pages/reports.html'
