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
    path('api/performance/', include('performance.urls')),
    path('api/ai/', include('ai.urls')),
    
    # Web routes (custom views) - Must be before Bloomerp to avoid conflicts
    path('admin-panel/', include(('core.admin_urls', 'admin_custom'), namespace='admin_custom')),
    path('projects/', include(('projects.urls', 'projects'), namespace='projects')),
    path('budgeting/', include(('budgeting.urls', 'budgeting'), namespace='budgeting')),
    path('clients/', include(('clients.web_urls', 'clients'), namespace='clients')),
    path('resources/', include(('resources.web_urls', 'resources'), namespace='resources')),
    path('performance/', include(('performance.web_urls', 'performance'), namespace='performance')),
    path('', include(('core.urls', 'core'), namespace='core')),
    
    # Bloomerp Framework routes (automatic CRUD views)
    # Temporarily disabled due to langgraph import compatibility issue
    # TODO: Re-enable after Bloomerp updates to support langgraph 1.0.6+
    # path('bloomerp/', include('bloomerp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

