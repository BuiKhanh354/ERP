from django.urls import path
from core.role_views.resource_manager_views import (
    ResourceDashboardView,
    ResourceAllocationListView,
    ResourceCapacityPlanningView,
    ResourceProjectResourcesView,
)

app_name = 'resource_manager_module'

urlpatterns = [
    path('dashboard/', ResourceDashboardView.as_view(), name='dashboard'),
    path('allocation-list/', ResourceAllocationListView.as_view(), name='allocation-list'),
    path('capacity-planning/', ResourceCapacityPlanningView.as_view(), name='capacity-planning'),
    path('project-resources/', ResourceProjectResourcesView.as_view(), name='project-resources'),
]
