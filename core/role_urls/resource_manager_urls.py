from django.urls import path
from core.role_views.resource_manager_views import (
    ResourceDashboardView,
    ResourceAllocationListView,
    ResourceCapacityPlanningView,
    ResourceProjectResourcesView,
    ResourceManagerProjectMembersView,
    ResourceManagerAddProjectMemberView,
    ResourceManagerPersonnelRecommendationView,
    ResourceManagerRecommendationDetailView,
    ResourceManagerApplyRecommendationView,
)

app_name = 'resource_manager_module'

urlpatterns = [
    path('dashboard/', ResourceDashboardView.as_view(), name='dashboard'),
    path('allocation-list/', ResourceAllocationListView.as_view(), name='allocation-list'),
    path('capacity-planning/', ResourceCapacityPlanningView.as_view(), name='capacity-planning'),
    path('project-resources/', ResourceProjectResourcesView.as_view(), name='project-resources'),
    path('projects/<int:project_id>/members/', ResourceManagerProjectMembersView.as_view(), name='project_members'),
    path('projects/<int:project_id>/add-member/', ResourceManagerAddProjectMemberView.as_view(), name='add_project_member'),
    path('projects/<int:project_id>/recommend-personnel/', ResourceManagerPersonnelRecommendationView.as_view(), name='recommend_personnel'),
    path('recommendations/<int:pk>/', ResourceManagerRecommendationDetailView.as_view(), name='recommendation_detail'),
    path('recommendations/<int:recommendation_id>/apply/', ResourceManagerApplyRecommendationView.as_view(), name='apply_recommendation'),
]
