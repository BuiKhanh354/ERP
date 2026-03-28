from django.urls import path
from core.role_views.finance_admin_views import (
    FinanceAdminDashboardView,
    BudgetApprovalView,
    ExpenseApprovalView,
    FinancialPeriodView,
    ActualCostView,
    FinancialReportsView,
)

app_name = 'finance_admin_module'

urlpatterns = [
    path('dashboard/', FinanceAdminDashboardView.as_view(), name='dashboard'),
    path('budget-approval/', BudgetApprovalView.as_view(), name='budget-approval'),
    path('expense-approval/', ExpenseApprovalView.as_view(), name='expense-approval'),
    path('financial-periods/', FinancialPeriodView.as_view(), name='financial-periods'),
    path('actual-costs/', ActualCostView.as_view(), name='actual-costs'),
    path('reports/', FinancialReportsView.as_view(), name='reports'),
]
