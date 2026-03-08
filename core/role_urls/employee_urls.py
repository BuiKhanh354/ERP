from django.urls import path
from core.role_views.employee_views import EmployeeDashboardView

app_name = 'employee_module'

urlpatterns = [
    path('dashboard/', EmployeeDashboardView.as_view(), name='dashboard'),
]
