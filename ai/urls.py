from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AIInsightViewSet
from .mini_views import (
    AnomalyDetectionAPIView,
    AttritionPredictAPIView,
    ChatAPIView,
    ProjectSummaryAPIView,
    RevenueForecastAPIView,
    ResourceRecommendationAPIView,
    RiskDetectionAPIView,
)

router = DefaultRouter()
router.register(r'insights', AIInsightViewSet, basename='insight')

urlpatterns = [
    path('', include(router.urls)),
    path('chat/', ChatAPIView.as_view(), name='ai-chat'),
    path('predict-attrition/', AttritionPredictAPIView.as_view(), name='ai-predict-attrition'),
    path('forecast/', RevenueForecastAPIView.as_view(), name='ai-forecast'),
    path('detect-anomaly/', AnomalyDetectionAPIView.as_view(), name='ai-detect-anomaly'),
    path('recommend-resource/', ResourceRecommendationAPIView.as_view(), name='ai-recommend-resource'),
    path('risk-detect/', RiskDetectionAPIView.as_view(), name='ai-risk-detect'),
    path('report/', ProjectSummaryAPIView.as_view(), name='ai-report'),
]

