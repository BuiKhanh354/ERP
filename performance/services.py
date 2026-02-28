"""Performance analytics business logic services."""
from django.db.models import Avg, Sum, Q
from django.utils import timezone
from .models import PerformanceMetric, PerformanceScore
from resources.models import Employee
from projects.models import Project, TimeEntry


class PerformanceService:
    """Service class for performance-related operations."""

    @staticmethod
    def calculate_employee_performance(employee_id, start_date=None, end_date=None):
        """Calculate overall performance for an employee."""
        employee = Employee.objects.get(id=employee_id)
        
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()

        scores = PerformanceScore.objects.filter(
            employee=employee,
            period_start__lte=end_date,
            period_end__gte=start_date
        )

        avg_score = scores.aggregate(avg=Avg('overall_score'))['avg'] or 0
        
        time_entries = TimeEntry.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )
        total_hours = float(time_entries.aggregate(total=Sum('hours'))['total'] or 0)
        
        return {
            'employee': employee,
            'average_score': avg_score,
            'total_hours': total_hours,
            'scores': scores,
        }

    @staticmethod
    def calculate_project_performance(project_id):
        """Calculate performance metrics for a project."""
        project = Project.objects.get(id=project_id)
        
        scores = PerformanceScore.objects.filter(project=project)
        avg_score = scores.aggregate(avg=Avg('overall_score'))['avg'] or 0
        
        tasks = project.tasks.all()
        completed_tasks = tasks.filter(status='done').count()
        total_tasks = tasks.count()
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            'project': project,
            'average_score': avg_score,
            'completion_rate': completion_rate,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
        }

    @staticmethod
    def recommend_salary_adjustment(employee_id):
        """Evaluate employee performance and recommend salary/bonus adjustments."""
        from datetime import timedelta
        from ai.services import AIService
        
        employee = Employee.objects.get(id=employee_id)
        
        # Get performance data
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)  # Last 3 months
        
        performance_data = PerformanceService.calculate_employee_performance(
            employee_id, start_date, end_date
        )
        
        # Get time entries
        time_entries = TimeEntry.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )
        total_hours = float(time_entries.aggregate(total=Sum('hours'))['total'] or 0)
        
        # Calculate productivity metrics
        from resources.models import ResourceAllocation
        projects_worked = ResourceAllocation.objects.filter(
            employee=employee,
            start_date__lte=end_date
        ).count()
        
        # Kiểm tra data trước khi phân tích
        if total_hours == 0 and not performance_data['scores'].exists():
            return {
                'employee': employee,
                'current_hourly_rate': float(employee.hourly_rate) if employee.hourly_rate else 0,
                'average_score': 0,
                'total_hours': 0,
                'projects_worked': projects_worked,
                'recommendation': 'review',
                'suggested_adjustment_percentage': 0,
                'bonus_recommendation': 0,
                'reasoning': f'Nhân viên {employee.full_name} chưa có dữ liệu ghi chép thời gian hoặc điểm hiệu suất. Vui lòng thêm dữ liệu trước khi phân tích.',
                'ai_insights': [],
                'ai_recommendations': [],
                'no_data': True
            }
        
        # Get AI analysis
        ai_analysis = AIService.analyze_resource_performance(employee_id)
        
        # Nếu AI analysis trả về no_data, vẫn tính recommendation dựa trên data hiện có
        if ai_analysis.get('no_data'):
            ai_analysis = {
                'insights': [],
                'recommendations': []
            }
        
        # Calculate recommendation
        avg_score = performance_data['average_score']
        current_hourly_rate = float(employee.hourly_rate) if employee.hourly_rate else 0
        
        recommendation = {
            'employee': employee,
            'current_hourly_rate': current_hourly_rate,
            'average_score': avg_score,
            'total_hours': total_hours,
            'projects_worked': projects_worked,
            'recommendation': 'maintain',  # maintain, increase, decrease
            'suggested_adjustment_percentage': 0,
            'bonus_recommendation': 0,
            'reasoning': '',
        }
        
        # Logic for recommendations
        if avg_score >= 90:
            recommendation['recommendation'] = 'increase'
            recommendation['suggested_adjustment_percentage'] = 10
            recommendation['bonus_recommendation'] = float(current_hourly_rate * total_hours * 0.1)  # 10% bonus
            recommendation['reasoning'] = 'Xuất sắc: Hiệu suất cao, đóng góp tích cực cho nhiều dự án.'
        elif avg_score >= 75:
            recommendation['recommendation'] = 'increase'
            recommendation['suggested_adjustment_percentage'] = 5
            recommendation['bonus_recommendation'] = float(current_hourly_rate * total_hours * 0.05)  # 5% bonus
            recommendation['reasoning'] = 'Tốt: Hiệu suất tốt, đóng góp ổn định.'
        elif avg_score >= 60:
            recommendation['recommendation'] = 'maintain'
            recommendation['reasoning'] = 'Đạt yêu cầu: Hiệu suất đạt mức cơ bản.'
        else:
            recommendation['recommendation'] = 'review'
            recommendation['reasoning'] = 'Cần cải thiện: Hiệu suất dưới mức mong đợi, cần đánh giá và hỗ trợ.'
        
        recommendation['ai_insights'] = ai_analysis.get('insights', [])
        recommendation['ai_recommendations'] = ai_analysis.get('recommendations', [])
        
        return recommendation
