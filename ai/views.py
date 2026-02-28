from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import AIInsight
from .serializers import AIInsightSerializer
from .services import AIService


class AIInsightViewSet(viewsets.ModelViewSet):
    queryset = AIInsight.objects.filter(is_active=True)
    serializer_class = AIInsightSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """GET /api/ai/insights/ - Trả về insights cho dashboard."""
        from django.utils import timezone
        from datetime import timedelta
        
        # Kiểm tra xem có force refresh không (từ query param)
        force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
        
        # Lấy insights mới nhất, ưu tiên general insights
        insights = AIInsight.objects.filter(
            is_active=True,
            created_by=request.user,
            insight_type='general'
        ).order_by('-created_at')[:5]
        
        # Luôn generate insight mới nếu:
        # 1. Không có insights nào
        # 2. Force refresh được yêu cầu
        # 3. Insight cũ hơn 5 phút (để tránh generate quá nhiều nhưng vẫn đảm bảo fresh)
        should_generate = False
        if not insights.exists():
            should_generate = True
        elif force_refresh:
            should_generate = True
        else:
            latest_insight = insights.first()
            # Nếu insight cũ hơn 5 phút, generate mới
            if latest_insight and latest_insight.created_at < timezone.now() - timedelta(minutes=5):
                should_generate = True
        
        if should_generate:
            try:
                from .services import AIService
                # Generate insight mới
                new_insight = AIService.generate_dashboard_insight(request.user)
                # Kiểm tra xem có data không
                if new_insight.get('no_data'):
                    # Nếu không có data, trả về thông báo
                    return Response({
                        'no_data': True,
                        'message': new_insight.get('summary', 'Chưa có đủ dữ liệu để phân tích.'),
                        'results': []
                    })
                # Lấy lại insights sau khi generate
                insights = AIInsight.objects.filter(
                    is_active=True,
                    created_by=request.user,
                    insight_type='general'
                ).order_by('-created_at')[:5]
            except Exception as e:
                # Nếu lỗi, vẫn trả về insights cũ nếu có
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error generating dashboard insight: {e}")
        
        serializer = self.get_serializer(insights, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def analyze_resource_performance(self, request):
        """Analyze resource performance and generate insights."""
        try:
            employee_id = request.data.get('employee_id')
            result = AIService.analyze_resource_performance(employee_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def recommend_project_staffing(self, request):
        """Recommend optimal project staffing."""
        try:
            project_id = request.data.get('project_id')
            result = AIService.recommend_project_staffing(project_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def analyze_budget_patterns(self, request):
        """Analyze budget patterns and suggest optimizations."""
        try:
            project_id = request.data.get('project_id')
            result = AIService.analyze_budget_patterns(project_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def analyze_sales_performance(self, request):
        """Analyze sales performance and provide improvement recommendations."""
        try:
            result = AIService.analyze_sales_performance(user=request.user)
            if result.get('no_data'):
                return Response(result, status=status.HTTP_200_OK)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def analyze_purchasing_patterns(self, request):
        """Analyze purchasing patterns and provide improvement recommendations."""
        try:
            result = AIService.analyze_purchasing_patterns(user=request.user)
            if result.get('no_data'):
                return Response(result, status=status.HTTP_200_OK)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def recommend_expense_optimization(self, request):
        """Recommend expense optimization with chart data."""
        try:
            project_id = request.data.get('project_id')
            result = AIService.recommend_expense_optimization(project_id=project_id, user=request.user)
            if result.get('no_data'):
                return Response(result, status=status.HTTP_200_OK)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
