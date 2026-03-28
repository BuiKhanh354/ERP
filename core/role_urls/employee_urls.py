from django.urls import path
from core.role_views.employee_views import (
    EmployeeDashboardView,
    EmployeeTimeEntryView,
    EmployeeTimeEntryListView,
)

app_name = 'employee_module'

urlpatterns = [
    path('dashboard/', EmployeeDashboardView.as_view(), name='dashboard'),
    path('time-entry/', EmployeeTimeEntryView.as_view(), name='time-entry'),
    path('time-entry-list/', EmployeeTimeEntryListView.as_view(), name='time-entry-list'),
]
