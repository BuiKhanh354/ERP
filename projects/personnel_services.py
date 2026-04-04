"""
Services for personnel recommendation and budget management.
"""
from decimal import Decimal
from django.db.models import Q, Avg, Sum
from django.utils import timezone
from resources.models import Employee, Department
from resources.salary_services import HourlyRateService
from performance.models import PerformanceScore
from .models import Project, PersonnelRecommendation, PersonnelRecommendationDetail


class PersonnelRecommendationService:
    """Service for recommending personnel for projects."""

    @staticmethod
    def calculate_employee_cost(employee, estimated_hours, allocation_percentage=100):
        """
        Tính chi phí nhân sự dựa trên lương/giờ và số giờ ước tính.
        
        Args:
            employee: Employee instance
            estimated_hours: Số giờ ước tính (Decimal)
            allocation_percentage: Tỷ lệ phân bổ (%) (mặc định 100)
        
        Returns:
            Decimal: Chi phí ước tính (VNĐ)
        """
        # Lấy lương/giờ hiện tại
        today = timezone.now().date()
        hourly_rate_obj = HourlyRateService.get_current_hourly_rate(employee)
        
        if hourly_rate_obj:
            hourly_rate = hourly_rate_obj.hourly_rate
        else:
            # Nếu chưa có lịch sử, tính từ lương tháng hiện tại
            result = HourlyRateService.calculate_hourly_rate(
                employee.hourly_rate,
                today.year,
                today.month
            )
            hourly_rate = result['hourly_rate']
        
        # Tính chi phí
        allocation_factor = Decimal(str(allocation_percentage)) / Decimal('100')
        cost = hourly_rate * Decimal(str(estimated_hours)) * allocation_factor
        
        return cost.quantize(Decimal('0.01'))

    @staticmethod
    def get_employee_performance_score(employee, project=None):
        """
        Lấy điểm hiệu suất của nhân sự.
        
        Args:
            employee: Employee instance
            project: Project instance (tùy chọn, để lấy điểm theo dự án)
        
        Returns:
            float: Điểm hiệu suất (0-100)
        """
        if project:
            scores = PerformanceScore.objects.filter(
                employee=employee,
                project=project
            )
        else:
            scores = PerformanceScore.objects.filter(employee=employee)
        
        avg_score = scores.aggregate(avg=Avg('overall_score'))['avg']
        return float(avg_score) if avg_score else 0.0

    @staticmethod
    def filter_employees_by_departments(employees, required_departments):
        """
        Lọc nhân sự theo phòng ban yêu cầu.
        
        Args:
            employees: QuerySet của Employee
            required_departments: QuerySet của Department
        
        Returns:
            QuerySet: Employees thuộc các phòng ban yêu cầu
        """
        if not required_departments.exists():
            return employees
        
        return employees.filter(department__in=required_departments)

    @staticmethod
    def rule_based_recommendation(project, optimization_goal='balanced', max_employees=10):
        """
        Đề xuất nhân sự dựa trên quy tắc (rule-based).
        
        Args:
            project: Project instance
            optimization_goal: 'performance', 'cost', hoặc 'balanced'
            max_employees: Số nhân sự tối đa đề xuất
        
        Returns:
            list: Danh sách dict với thông tin đề xuất
        """
        # Lấy nhân sự từ các phòng ban yêu cầu
        employees = Employee.objects.filter(is_active=True)
        if project.required_departments.exists():
            employees = PersonnelRecommendationService.filter_employees_by_departments(
                employees,
                project.required_departments.all()
            )
        
        recommendations = []
        
        # Bước 1: Tính toán tất cả thông tin trước
        for employee in employees[:max_employees * 2]:  # Lấy nhiều hơn để filter
            # Tính điểm hiệu suất
            performance_score = PersonnelRecommendationService.get_employee_performance_score(
                employee,
                project
            )
            
            # Tính chi phí ước tính (giả sử 160 giờ/tháng)
            estimated_hours = Decimal('160')
            estimated_cost = PersonnelRecommendationService.calculate_employee_cost(
                employee,
                estimated_hours,
                allocation_percentage=100
            )
            
            recommendations.append({
                'employee': employee,
                'performance_score': performance_score,
                'estimated_cost': estimated_cost,
                'estimated_hours': estimated_hours,
                'allocation_percentage': 100,  # Mặc định
                'reasoning': f"Hiệu suất: {performance_score:.1f}/100, Chi phí: {estimated_cost:,.0f} VNĐ"
            })
        
        # Bước 2: Tính max_cost để normalize (sau khi đã có tất cả chi phí)
        if recommendations:
            max_cost = max(r['estimated_cost'] for r in recommendations)
            min_cost = min(r['estimated_cost'] for r in recommendations)
        else:
            max_cost = Decimal('50000000')
            min_cost = Decimal('0')
        
        # Bước 3: Tính điểm tổng hợp và sắp xếp
        for rec in recommendations:
            if optimization_goal == 'performance':
                # Ưu tiên hiệu suất - sắp xếp theo performance_score giảm dần
                rec['combined_score'] = rec['performance_score']
            elif optimization_goal == 'cost':
                # Ưu tiên chi phí thấp - chi phí càng thấp, score càng cao
                if max_cost > min_cost:
                    # Normalize: chi phí thấp nhất = 100, chi phí cao nhất = 0
                    cost_score = (1 - float(rec['estimated_cost'] - min_cost) / float(max_cost - min_cost)) * 100
                else:
                    cost_score = 100
                # Ưu tiên 95% chi phí, 5% hiệu suất tối thiểu (chỉ để đảm bảo chất lượng)
                rec['combined_score'] = cost_score * 0.95 + min(rec['performance_score'], 50) * 0.05
            else:  # balanced
                # Cân bằng - kết hợp hiệu suất và chi phí
                if max_cost > min_cost:
                    cost_score = (1 - float(rec['estimated_cost'] - min_cost) / float(max_cost - min_cost)) * 100
                else:
                    cost_score = 100
                rec['combined_score'] = (rec['performance_score'] * 0.6 + cost_score * 0.4)
        
        # Sắp xếp theo điểm tổng hợp (giảm dần)
        recommendations.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Chỉ lấy top N
        return recommendations[:max_employees]

    @staticmethod
    def ai_recommendation(project, optimization_goal='balanced', rule_based_results=None):
        """
        Đề xuất nhân sự bằng lớp AI hiện tại.
        
        Args:
            project: Project instance
            optimization_goal: 'performance', 'cost', hoặc 'balanced'
            rule_based_results: Kết quả từ rule-based (tùy chọn)
        
        Returns:
            dict: {
                'recommendations': list,
                'reasoning': str,
                'total_cost': Decimal
            }
        """
        from ai.services import AIService
        
        # Chuẩn bị context
        context = {
            'project_name': project.name,
            'project_description': project.description,
            'budget_for_personnel': float(project.budget_for_personnel),
            'required_departments': [dept.name for dept in project.required_departments.all()],
            'optimization_goal': optimization_goal,
        }
        
        # Lấy danh sách nhân sự khả dụng
        employees = Employee.objects.filter(is_active=True)
        if project.required_departments.exists():
            employees = PersonnelRecommendationService.filter_employees_by_departments(
                employees,
                project.required_departments.all()
            )
        
        employee_data = []
        for emp in employees[:20]:  # Giới hạn để không quá dài
            perf_score = PersonnelRecommendationService.get_employee_performance_score(emp)
            hourly_rate_obj = HourlyRateService.get_current_hourly_rate(emp)
            hourly_rate = hourly_rate_obj.hourly_rate if hourly_rate_obj else 0
            
            employee_data.append({
                'id': emp.id,
                'name': emp.full_name,
                'department': emp.department.name if emp.department else 'N/A',
                'position': emp.position,
                'performance_score': perf_score,
                'hourly_rate': float(hourly_rate),
            })
        
        context['available_employees'] = employee_data
        
        # Gọi AI service (cần tạo method mới trong AIService)
        try:
            ai_result = AIService.recommend_personnel_for_project(context)
            return ai_result
        except Exception as e:
            # Fallback về rule-based nếu AI lỗi
            if rule_based_results:
                return {
                    'recommendations': rule_based_results,
                    'reasoning': 'Sử dụng thuật toán rule-based do lỗi AI.',
                    'total_cost': sum(r['estimated_cost'] for r in rule_based_results)
                }
            return None

    @staticmethod
    def recommend_personnel(project, optimization_goal='balanced', use_ai=True):
        """
        Đề xuất nhân sự cho dự án (kết hợp rule-based + AI).
        
        Args:
            project: Project instance
            optimization_goal: 'performance', 'cost', hoặc 'balanced'
            use_ai: Có sử dụng AI không (mặc định True)
        
        Returns:
            dict: {
                'recommendations': list,
                'reasoning': str,
                'total_cost': Decimal,
                'method': str
            }
        """
        # Bước 1: Rule-based recommendation
        rule_based_results = PersonnelRecommendationService.rule_based_recommendation(
            project,
            optimization_goal
        )
        
        # Bước 2: AI recommendation (nếu được yêu cầu)
        if use_ai:
            ai_result = PersonnelRecommendationService.ai_recommendation(
                project,
                optimization_goal,
                rule_based_results
            )
            
            if ai_result and ai_result.get('recommendations'):
                from django.utils import timezone
                timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
                reasoning = ai_result.get('reasoning', '')
                if reasoning:
                    reasoning = f"{reasoning} (Tạo lúc {timestamp})"
                else:
                    reasoning = f"Đề xuất từ AI (tạo lúc {timestamp})"
                return {
                    'recommendations': ai_result['recommendations'],
                    'reasoning': reasoning,
                    'total_cost': Decimal(str(ai_result.get('total_cost', 0))),
                    'method': 'ai'
                }
        
        # Fallback về rule-based
        total_cost = sum(r['estimated_cost'] for r in rule_based_results)
        from django.utils import timezone
        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        return {
            'recommendations': rule_based_results,
            'reasoning': f'Đề xuất dựa trên {optimization_goal} (tạo lúc {timestamp}).',
            'total_cost': total_cost,
            'method': 'rule-based'
        }

    @staticmethod
    def save_recommendation(project, optimization_goal, recommendations_data, user):
        """
        Lưu đề xuất nhân sự vào database.
        
        Args:
            project: Project instance
            optimization_goal: 'performance', 'cost', hoặc 'balanced'
            recommendations_data: dict từ recommend_personnel()
            user: User instance (created_by)
        
        Returns:
            PersonnelRecommendation instance
        """
        recommendation = PersonnelRecommendation.objects.create(
            project=project,
            optimization_goal=optimization_goal,
            total_estimated_cost=recommendations_data['total_cost'],
            reasoning=recommendations_data['reasoning'],
            created_by=user
        )
        
        # Tạo chi tiết đề xuất
        for rec in recommendations_data['recommendations']:
            PersonnelRecommendationDetail.objects.create(
                recommendation=recommendation,
                employee=rec['employee'],
                allocation_percentage=rec.get('allocation_percentage', 100),
                estimated_hours=rec.get('estimated_hours', 160),
                estimated_cost=rec['estimated_cost'],
                reasoning=rec.get('reasoning', ''),
                created_by=user
            )
        
        return recommendation


class BudgetMonitoringService:
    """Service for monitoring project budget."""

    @staticmethod
    def calculate_personnel_budget_usage(project):
        """
        Tinh muc su dung ngan sach nhan su cua du an.
        """
        allocated_budget = project.budget_for_personnel or Decimal('0')

        used_budget = Decimal('0')
        today = timezone.now().date()
        allocations = project.allocations.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).select_related('employee')

        for allocation in allocations:
            estimated_hours = Decimal('160')
            cost = PersonnelRecommendationService.calculate_employee_cost(
                allocation.employee,
                estimated_hours,
                allocation.allocation_percentage
            )
            used_budget += cost

        remaining_budget = allocated_budget - used_budget
        usage_percentage = (float(used_budget) / float(allocated_budget) * 100) if allocated_budget > 0 else 0
        is_over_budget = used_budget > allocated_budget

        return {
            'allocated_budget': allocated_budget,
            'used_budget': used_budget,
            'remaining_budget': remaining_budget,
            'usage_percentage': usage_percentage,
            'is_over_budget': is_over_budget
        }

    @staticmethod
    def calculate_budget_limits_report(project):
        """
        Detailed report with budget limits by employee/task/total.
        """
        budget_info = BudgetMonitoringService.calculate_personnel_budget_usage(project)
        allocated_budget = budget_info['allocated_budget']

        per_employee_limit = (allocated_budget * Decimal('0.40')).quantize(Decimal('0.01')) if allocated_budget > 0 else Decimal('0')
        task_count = max(project.tasks.count(), 1)
        per_task_limit = (allocated_budget / Decimal(str(task_count))).quantize(Decimal('0.01')) if allocated_budget > 0 else Decimal('0')

        employee_costs = []
        task_costs = []
        warnings = []

        today = timezone.now().date()
        allocations = project.allocations.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).select_related('employee')

        for allocation in allocations:
            estimated_hours = Decimal('160')
            cost = PersonnelRecommendationService.calculate_employee_cost(
                allocation.employee,
                estimated_hours,
                allocation.allocation_percentage
            )
            is_over_limit = per_employee_limit > 0 and cost > per_employee_limit
            employee_costs.append({
                'employee_id': allocation.employee_id,
                'employee_name': allocation.employee.full_name,
                'allocation_percentage': float(allocation.allocation_percentage),
                'estimated_cost': float(cost),
                'limit': float(per_employee_limit),
                'is_over_limit': is_over_limit,
            })
            if is_over_limit:
                warnings.append(f"Employee {allocation.employee.full_name} exceeds per-employee budget limit.")

        tasks = project.tasks.select_related('assigned_to')
        for task in tasks:
            if not task.assigned_to:
                continue
            task_hours = task.estimated_hours or Decimal('0')
            task_cost = PersonnelRecommendationService.calculate_employee_cost(
                task.assigned_to,
                task_hours,
                allocation_percentage=100
            )
            is_over_task_limit = per_task_limit > 0 and task_cost > per_task_limit
            task_costs.append({
                'task_id': task.id,
                'task_name': task.name,
                'employee_name': task.assigned_to.full_name,
                'estimated_hours': float(task_hours),
                'estimated_cost': float(task_cost),
                'limit': float(per_task_limit),
                'is_over_limit': is_over_task_limit,
            })
            if is_over_task_limit:
                warnings.append(f"Task '{task.name}' exceeds per-task budget limit.")

        if budget_info['is_over_budget']:
            warnings.append("Total personnel budget exceeded.")

        return {
            'allocated_budget': float(allocated_budget),
            'used_budget': float(budget_info['used_budget']),
            'remaining_budget': float(budget_info['remaining_budget']),
            'usage_percentage': budget_info['usage_percentage'],
            'is_over_budget': budget_info['is_over_budget'],
            'per_employee_limit': float(per_employee_limit),
            'per_task_limit': float(per_task_limit),
            'employee_costs': employee_costs,
            'task_costs': task_costs,
            'warnings': warnings,
        }

    @staticmethod
    def check_budget_warning(project, threshold=0.8):
        """
        Kiem tra canh bao ngan sach.
        """
        budget_info = BudgetMonitoringService.calculate_personnel_budget_usage(project)
        limits_report = BudgetMonitoringService.calculate_budget_limits_report(project)

        if budget_info['is_over_budget']:
            return {
                'has_warning': True,
                'message': f'Ngan sach nhan su da vuot qua {budget_info["allocated_budget"]:,.0f} VND!',
                'severity': 'danger'
            }
        elif limits_report['warnings']:
            return {
                'has_warning': True,
                'message': limits_report['warnings'][0],
                'severity': 'warning'
            }
        elif budget_info['usage_percentage'] >= threshold * 100:
            return {
                'has_warning': True,
                'message': f'Ngan sach nhan su da su dung {budget_info["usage_percentage"]:.1f}% ({budget_info["used_budget"]:,.0f} VND / {budget_info["allocated_budget"]:,.0f} VND)',
                'severity': 'warning'
            }

        return {
            'has_warning': False,
            'message': '',
            'severity': None
        }
