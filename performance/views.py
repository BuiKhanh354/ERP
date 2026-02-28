from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PerformanceMetric, PerformanceScore
from .serializers import PerformanceMetricSerializer, PerformanceScoreSerializer
from .services import PerformanceService


class PerformanceMetricViewSet(viewsets.ModelViewSet):
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    permission_classes = [IsAuthenticated]


class PerformanceScoreViewSet(viewsets.ModelViewSet):
    queryset = PerformanceScore.objects.all()
    serializer_class = PerformanceScoreSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def recommend_salary_adjustment(self, request):
        """Recommend salary/bonus adjustment based on employee performance."""
        try:
            employee_id = request.data.get('employee_id')
            result = PerformanceService.recommend_salary_adjustment(employee_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
