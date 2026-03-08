"""URL configuration for the CFO module."""
from django.urls import path
from .cfo_views import (
    CFODashboardView,
    ProjectFinanceView,
    ProjectFinanceDetailView,
    BudgetMonitoringView,
    ApprovalCenterView,
    ApproveExpenseView,
    RejectExpenseView,
    ApproveBudgetActionView,
    RejectBudgetView,
    FinancialReportsView,
    CFOReportExportView,
)

app_name = 'cfo'

urlpatterns = [
    path('', CFODashboardView.as_view(), name='dashboard'),
    path('project-finance/', ProjectFinanceView.as_view(), name='project_finance'),
    path('project-finance/<int:pk>/', ProjectFinanceDetailView.as_view(), name='project_finance_detail'),
    path('budget/', BudgetMonitoringView.as_view(), name='budget_monitoring'),
    path('approvals/', ApprovalCenterView.as_view(), name='approval_center'),
    path('approvals/expense/<int:pk>/approve/', ApproveExpenseView.as_view(), name='approve_expense'),
    path('approvals/expense/<int:pk>/reject/', RejectExpenseView.as_view(), name='reject_expense'),
    path('approvals/budget/<int:pk>/approve/', ApproveBudgetActionView.as_view(), name='approve_budget'),
    path('approvals/budget/<int:pk>/reject/', RejectBudgetView.as_view(), name='reject_budget'),
    path('reports/', FinancialReportsView.as_view(), name='reports'),
    path('reports/export/', CFOReportExportView.as_view(), name='report_export'),
]
