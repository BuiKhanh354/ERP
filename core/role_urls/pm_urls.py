from django.urls import path
from core.role_views.pm_views import PMDashboardView

app_name = 'pm_module'

urlpatterns = [
    path('dashboard/', PMDashboardView.as_view(), name='dashboard'),
]
