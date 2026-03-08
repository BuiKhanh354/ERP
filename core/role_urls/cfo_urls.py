from django.urls import path
# Import existing advanced CFO Dashboard and other views
from accounting.cfo_views import (
    CFODashboardView,
    CFOProjectFinanceDetailView,
)

app_name = 'cfo_module'

urlpatterns = [
    path('dashboard/', CFODashboardView.as_view(), name='dashboard'),
    path('project-finance/', CFODashboardView.as_view(), name='project_finance'), # Temp fallback
    path('budget-monitoring/', CFODashboardView.as_view(), name='budget_monitoring'), # Temp fallback
    path('approvals/', CFODashboardView.as_view(), name='approval_center'), # Temp fallback
    path('reports/', CFODashboardView.as_view(), name='reports'), # Temp fallback
]
