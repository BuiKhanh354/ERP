"""AI Insights views for displaying AI analysis results."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
import json

from ai.services import AIService
from performance.services import PerformanceService
from resources.models import Employee
from projects.models import Project
from budgeting.models import Budget


class SalesAnalysisView(LoginRequiredMixin, TemplateView):
    """View for sales performance analysis."""
    template_name = 'pages/ai_sales_analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Phân tích Hiệu suất Bán hàng'
        return context


class PurchasingAnalysisView(LoginRequiredMixin, TemplateView):
    """View for purchasing pattern analysis."""
    template_name = 'pages/ai_purchasing_analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Phân tích Mua hàng'
        return context


class ExpenseOptimizationView(LoginRequiredMixin, TemplateView):
    """View for expense optimization recommendations."""
    template_name = 'pages/ai_expense_optimization.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gợi ý Tối ưu Chi tiêu'
        context['projects'] = Project.objects.all()
        return context


class SalaryRecommendationView(LoginRequiredMixin, TemplateView):
    """View for salary/bonus recommendations."""
    template_name = 'pages/ai_salary_recommendation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Đề xuất Lương & Thưởng'
        context['employees'] = Employee.objects.filter(is_active=True)
        
        # Pre-select employee if provided in query params
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            try:
                context['selected_employee'] = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                pass
        
        return context


class AISalesAnalysisAPIView(LoginRequiredMixin, View):
    """API endpoint for sales analysis."""
    
    def post(self, request):
        try:
            result = AIService.analyze_sales_performance(user=request.user)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class AIPurchasingAnalysisAPIView(LoginRequiredMixin, View):
    """API endpoint for purchasing analysis."""
    
    def post(self, request):
        try:
            result = AIService.analyze_purchasing_patterns(user=request.user)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class AIExpenseOptimizationAPIView(LoginRequiredMixin, View):
    """API endpoint for expense optimization."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            project_id = data.get('project_id')
            result = AIService.recommend_expense_optimization(project_id=project_id, user=request.user)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class AISalaryRecommendationAPIView(LoginRequiredMixin, View):
    """API endpoint for salary recommendations."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            employee_id = data.get('employee_id')
            if not employee_id:
                return JsonResponse({'error': 'employee_id is required'}, status=400)
            
            result = PerformanceService.recommend_salary_adjustment(employee_id)
            
            # Convert to JSON-serializable format
            return JsonResponse({
                'employee_id': result['employee'].id,
                'employee_name': result['employee'].full_name,
                'current_hourly_rate': float(result['current_hourly_rate']),
                'average_score': float(result['average_score']),
                'total_hours': float(result['total_hours']),
                'projects_worked': result['projects_worked'],
                'recommendation': result['recommendation'],
                'suggested_adjustment_percentage': result['suggested_adjustment_percentage'],
                'bonus_recommendation': float(result['bonus_recommendation']),
                'reasoning': result['reasoning'],
                'ai_insights': result.get('ai_insights', []),
                'ai_recommendations': result.get('ai_recommendations', []),
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
