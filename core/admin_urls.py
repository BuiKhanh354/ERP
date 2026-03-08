"""
URLs cho Admin Panel — System Administration only.
Theo fixgiaodien.md: User, Role, Department, Project Access, Audit, Settings.
"""
from django.urls import path
from . import admin_views

app_name = 'admin_custom'

urlpatterns = [
    # Dashboard
    path('', admin_views.AdminDashboardView.as_view(), name='dashboard'),
    
    # User Management
    path('users/', admin_views.AdminUserListView.as_view(), name='users'),
    path('users/create/', admin_views.AdminUserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', admin_views.AdminUserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', admin_views.AdminUserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/deactivate/', admin_views.AdminUserDeactivateView.as_view(), name='user_deactivate'),
    
    # Role & Permission Management
    path('roles/', admin_views.AdminRoleListView.as_view(), name='roles'),
    path('roles/<int:pk>/', admin_views.AdminRoleDetailView.as_view(), name='role_detail'),
    
    # Department Management
    path('departments/', admin_views.AdminDepartmentListView.as_view(), name='departments'),
    path('departments/create/', admin_views.AdminDepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', admin_views.AdminDepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/delete/', admin_views.AdminDepartmentDeleteView.as_view(), name='department_delete'),
    
    # Project Access Control
    path('project-access/', admin_views.AdminProjectAccessView.as_view(), name='project_access'),
    
    # Audit Log
    path('audit-log/', admin_views.AdminAuditLogView.as_view(), name='audit_log'),
    
    # System Settings
    path('settings/', admin_views.AdminSystemSettingsView.as_view(), name='system_settings'),
]
