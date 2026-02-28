"""Web URL patterns for Resource Management."""
from django.urls import path
from .web_views import (
    EmployeeListView, EmployeeDetailView, EmployeeCreateView,
    EmployeeUpdateView, EmployeeDeleteView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView, DepartmentDeleteView,
    CreatePositionView, PayrollScheduleView
)
from .salary_views import SalaryTrackingView

app_name = 'resources'

urlpatterns = [
    # Employees
    path('', EmployeeListView.as_view(), name='list'),
    path('<int:pk>/', EmployeeDetailView.as_view(), name='detail'),
    path('create/', EmployeeCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', EmployeeUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', EmployeeDeleteView.as_view(), name='delete'),
    
    # Departments
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),
    
    # Positions (API)
    path('api/create-position/', CreatePositionView.as_view(), name='create_position'),
    
    # Salary tracking for employees
    path('salary-tracking/', SalaryTrackingView.as_view(), name='salary-tracking'),
    
    # Payroll schedule management (chung cho toàn bộ nhân viên)
    path('payroll-schedule/', PayrollScheduleView.as_view(), name='payroll-schedule'),
]
