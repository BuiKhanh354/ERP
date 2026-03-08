from django.urls import path
from core.role_views.hr_views import HRDashboardView

app_name = 'hr_module'

urlpatterns = [
    path('dashboard/', HRDashboardView.as_view(), name='dashboard'),
]
