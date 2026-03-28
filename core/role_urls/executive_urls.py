from django.urls import path
from core.role_views.executive_views import (
    ExecutiveDashboardView,
    ExecutiveProjectPortfolioView,
    ExecutiveFinancialReportsView,
    ExecutivePerformanceView,
)

app_name = 'executive_module'

urlpatterns = [
    path('dashboard/', ExecutiveDashboardView.as_view(), name='dashboard'),
    path('project-portfolio/', ExecutiveProjectPortfolioView.as_view(), name='project-portfolio'),
    path('financial-reports/', ExecutiveFinancialReportsView.as_view(), name='financial-reports'),
    path('performance/', ExecutivePerformanceView.as_view(), name='performance'),
]
