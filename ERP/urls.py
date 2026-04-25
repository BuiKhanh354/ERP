"""
URL configuration for ERP project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import LoginView

urlpatterns = [
    # Admin login dùng chung giao diện login ERP
    path('admin/login/', LoginView.as_view(), name='admin-login'),
    path('admin/', admin.site.urls),

    # REST API routes
    path('api/core/', include(('core.urls', 'core'), namespace='core-api')),
    path('api/projects/', include(('projects.urls', 'projects'), namespace='projects-api')),
    path('api/resources/', include('resources.urls')),
    path('api/budgeting/', include('budgeting.urls')),
    path('api/clients/', include('clients.urls')),
    path('api/ai/', include('ai.urls')),
    
    # Role-based web routes (4-role architecture)
    path('admin-panel/', include(('core.role_urls.admin_urls', 'admin_module'), namespace='admin_custom')),
    path('employee/', include(('core.role_urls.employee_urls', 'employee_module'), namespace='employee_module')),
    path('manager/', include(('core.role_urls.pm_urls', 'pm_module'), namespace='pm_module')),
    
    # Legacy routes (backward compat, sẽ deprecate dần)
    path('projects/', include(('projects.urls', 'projects'), namespace='projects')),
    path('budgeting/', include(('budgeting.urls', 'budgeting'), namespace='budgeting')),
    path('clients/', include(('clients.web_urls', 'clients'), namespace='clients')),
    path('resources/', include(('resources.web_urls', 'resources'), namespace='resources')),
    path('', include(('core.urls', 'core'), namespace='core')),
    
    # Bloomerp Framework routes (automatic CRUD views)
    # Temporarily disabled due to langgraph import compatibility issue
    # TODO: Re-enable after Bloomerp updates to support langgraph 1.0.6+
    # path('bloomerp/', include('bloomerp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
