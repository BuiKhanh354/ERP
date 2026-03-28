from django.urls import path
from core.role_views.admin_views import AdminDashboardView
from core.role_views.admin_department_views import (
    AdminDepartmentListView,
    AdminDepartmentCreateView,
    AdminDepartmentUpdateView,
    AdminDepartmentDetailView,
    AdminDepartmentToggleStatusView,
    AdminDepartmentHierarchyView,
    DepartmentEmployeeListView,
    AddEmployeeToDepartmentView,
    RemoveEmployeeFromDepartmentView,
)
from core.role_views.admin_analytics_views import AdminAnalyticsView
from core.role_views.admin_user_views import (
    AdminUserListView,
    AdminUserCreateView,
    AdminUserEditView,
    AdminUserToggleStatusView,
    AdminUserResetPasswordView,
    AdminAuditLogListView,
)

app_name = 'admin_module'

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='dashboard'),

    # User Management
    path('users/', AdminUserListView.as_view(), name='user_list'),
    path('users/create/', AdminUserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', AdminUserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle-status/', AdminUserToggleStatusView.as_view(), name='user_toggle_status'),
    path('users/<int:pk>/reset-password/', AdminUserResetPasswordView.as_view(), name='user_reset_password'),

    # Department management
    path('departments/', AdminDepartmentListView.as_view(), name='department_list'),
    path('departments/create/', AdminDepartmentCreateView.as_view(), name='department_create'),
    path('departments/hierarchy/', AdminDepartmentHierarchyView.as_view(), name='department_hierarchy'),
    path('departments/<int:pk>/', AdminDepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/edit/', AdminDepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/toggle-status/', AdminDepartmentToggleStatusView.as_view(), name='department_toggle_status'),

    # Department employee management
    path('departments/<int:pk>/employees/', DepartmentEmployeeListView.as_view(), name='department_employees'),
    path('departments/<int:pk>/add-employee/', AddEmployeeToDepartmentView.as_view(), name='department_add_employee'),
    path('departments/<int:pk>/remove-employee/<int:employee_id>/', RemoveEmployeeFromDepartmentView.as_view(), name='department_remove_employee'),

    # Analytics
    path('analytics/', AdminAnalyticsView.as_view(), name='analytics'),

    # System
    path('logs/', AdminAuditLogListView.as_view(), name='audit_logs'),
]
