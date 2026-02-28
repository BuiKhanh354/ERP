"""Web URL patterns for Performance management."""
from django.urls import path
from .web_views import (
    PerformanceScoreCreateView,
    PerformanceScoreUpdateView,
    PerformanceScoreDeleteView,
    PerformanceScoreListView,
)

app_name = 'performance'

urlpatterns = [
    path('scores/', PerformanceScoreListView.as_view(), name='score_list'),
    path('scores/create/', PerformanceScoreCreateView.as_view(), name='score_create'),
    path('scores/<int:pk>/edit/', PerformanceScoreUpdateView.as_view(), name='score_edit'),
    path('scores/<int:pk>/delete/', PerformanceScoreDeleteView.as_view(), name='score_delete'),
]
