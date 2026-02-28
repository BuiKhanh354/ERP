from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PerformanceMetricViewSet, PerformanceScoreViewSet

router = DefaultRouter()
router.register(r'metrics', PerformanceMetricViewSet, basename='metric')
router.register(r'scores', PerformanceScoreViewSet, basename='score')

urlpatterns = [
    path('', include(router.urls)),
]

