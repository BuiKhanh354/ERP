from django.http import JsonResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .models import AIInsight
from .serializers import AIInsightSerializer


def _refactor_disabled_response():
    return JsonResponse(
        {"message": "Feature temporarily disabled to refactor AI"},
        status=501,
    )


class AIInsightViewSet(viewsets.ModelViewSet):
    queryset = AIInsight.objects.filter(is_active=True)
    serializer_class = AIInsightSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def analyze_resource_performance(self, request):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def recommend_project_staffing(self, request):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def analyze_budget_patterns(self, request):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def analyze_sales_performance(self, request):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def analyze_purchasing_patterns(self, request):
        return _refactor_disabled_response()

    @action(detail=False, methods=["post"])
    def recommend_expense_optimization(self, request):
        return _refactor_disabled_response()
