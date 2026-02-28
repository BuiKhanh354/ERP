"""
URLs cho Admin Panel với đầy đủ CRUD operations.
"""
from django.urls import path
from . import admin_views

app_name = 'admin_custom'

urlpatterns = [
    # Dashboard
    path('', admin_views.AdminDashboardView.as_view(), name='dashboard'),
    
    # User Management
    path('users/', admin_views.AdminUserListView.as_view(), name='users'),
    path('users/<int:pk>/', admin_views.AdminUserDetailView.as_view(), name='user_detail'),
    
    # Project Management
    path('projects/', admin_views.AdminProjectListView.as_view(), name='projects'),
    path('projects/create/', admin_views.AdminProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/edit/', admin_views.AdminProjectUpdateView.as_view(), name='project_edit'),
    path('projects/<int:pk>/delete/', admin_views.AdminProjectDeleteView.as_view(), name='project_delete'),
    
    # Task Management
    path('tasks/', admin_views.AdminTaskListView.as_view(), name='tasks'),
    path('tasks/create/', admin_views.AdminTaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/edit/', admin_views.AdminTaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/delete/', admin_views.AdminTaskDeleteView.as_view(), name='task_delete'),
    
    # Employee Management
    path('employees/', admin_views.AdminEmployeeListView.as_view(), name='employees'),
    path('employees/create/', admin_views.AdminEmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/edit/', admin_views.AdminEmployeeUpdateView.as_view(), name='employee_edit'),
    path('employees/<int:pk>/delete/', admin_views.AdminEmployeeDeleteView.as_view(), name='employee_delete'),
    
    # Client Management
    path('clients/', admin_views.AdminClientListView.as_view(), name='clients'),
    path('clients/create/', admin_views.AdminClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/edit/', admin_views.AdminClientUpdateView.as_view(), name='client_edit'),
    path('clients/<int:pk>/delete/', admin_views.AdminClientDeleteView.as_view(), name='client_delete'),
    
    # Budget Management
    path('budgets/', admin_views.AdminBudgetListView.as_view(), name='budgets'),
    path('budgets/create/', admin_views.AdminBudgetCreateView.as_view(), name='budget_create'),
    path('budgets/<int:pk>/edit/', admin_views.AdminBudgetUpdateView.as_view(), name='budget_edit'),
    path('budgets/<int:pk>/delete/', admin_views.AdminBudgetDeleteView.as_view(), name='budget_delete'),
    
    # Department Management
    path('departments/', admin_views.AdminDepartmentListView.as_view(), name='departments'),
    path('departments/create/', admin_views.AdminDepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', admin_views.AdminDepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/delete/', admin_views.AdminDepartmentDeleteView.as_view(), name='department_delete'),
    
    # Export Functions
    path('export/projects/', admin_views.export_projects_csv, name='export_projects'),
    path('export/employees/', admin_views.export_employees_csv, name='export_employees'),
    path('export/clients/', admin_views.export_clients_csv, name='export_clients'),
]
