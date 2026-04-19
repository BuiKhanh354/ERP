"""
Services for personnel recommendation and budget management.
"""
from decimal import Decimal
from django.db.models import Q, Avg, Sum
from django.utils import timezone
from resources.models import Employee, Department, EmployeeSkill, ResourceAllocation
from resources.salary_services import HourlyRateService
from performance.models import PerformanceScore
from .models import Project, Task, PersonnelRecommendation, PersonnelRecommendationDetail


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
    def extract_required_skills(project):
        """Extract required skill keywords from project tasks."""
        required = set()
        task_rows = Task.objects.filter(project=project).exclude(required_skills='').values_list('required_skills', flat=True)
        for raw in task_rows:
            if not raw:
                continue
            chunks = str(raw).replace(';', ',').split(',')
            for chunk in chunks:
                token = chunk.strip().lower()
                if token:
                    required.add(token)
        return required

    @staticmethod
    def get_employee_skill_keywords(employee):
        """Get normalized skill keywords for employee."""
        skills = set()
        skill_rows = EmployeeSkill.objects.filter(employee=employee).select_related('skill')
        for row in skill_rows:
            skills.add((row.skill.name or '').strip().lower())
            if row.skill.category:
                skills.add((row.skill.category or '').strip().lower())
        # Position can also contain useful keywords
        if employee.position:
            for token in str(employee.position).replace('/', ' ').replace('-', ' ').split():
                t = token.strip().lower()
                if t:
                    skills.add(t)
        return skills

    @staticmethod
    def calculate_skill_match_score(required_skills, employee_keywords):
        """Return score in range 0..100 based on keyword overlap."""
        if not required_skills:
            return 60.0
        matched = sum(1 for sk in required_skills if sk in employee_keywords)
        return round((matched / max(len(required_skills), 1)) * 100, 2)

    @staticmethod
    def get_employee_workload_score(employee):
        """Convert current allocation load to 0..100 availability score."""
        today = timezone.localdate()
        total_alloc = (
            ResourceAllocation.objects.filter(employee=employee)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .aggregate(total=Sum('allocation_percentage'))['total']
            or 0
        )
        availability = max(0, 100 - float(total_alloc))
        return round(availability, 2), round(float(total_alloc), 2)

    @staticmethod
    def rule_based_recommendation(project, optimization_goal='balanced', max_employees=10):
        """
        De xuat nhan su dua tren scoring noi bo (khong train model).
        """
        employees = Employee.objects.filter(is_active=True).select_related('department')
        if project.required_departments.exists():
            employees = PersonnelRecommendationService.filter_employees_by_departments(
                employees,
                project.required_departments.all()
            )

        required_skills = PersonnelRecommendationService.extract_required_skills(project)
        recommendations = []

        for employee in employees[: max_employees * 4]:
            performance_score = PersonnelRecommendationService.get_employee_performance_score(employee, project)
            availability_score, current_load = PersonnelRecommendationService.get_employee_workload_score(employee)
            employee_keywords = PersonnelRecommendationService.get_employee_skill_keywords(employee)
            skill_match_score = PersonnelRecommendationService.calculate_skill_match_score(required_skills, employee_keywords)

            estimated_hours = Decimal('160')
            estimated_cost = PersonnelRecommendationService.calculate_employee_cost(
                employee,
                estimated_hours,
                allocation_percentage=100
            )

            recommendations.append(
                {
                    'employee': employee,
                    'performance_score': float(performance_score),
                    'availability_score': float(availability_score),
                    'current_load': float(current_load),
                    'skill_match_score': float(skill_match_score),
                    'estimated_cost': estimated_cost,
                    'estimated_hours': estimated_hours,
                    'allocation_percentage': 100,
                }
            )

        if not recommendations:
            return []

        max_cost = max(r['estimated_cost'] for r in recommendations)
        min_cost = min(r['estimated_cost'] for r in recommendations)

        for rec in recommendations:
            if max_cost > min_cost:
                cost_score = (1 - float(rec['estimated_cost'] - min_cost) / float(max_cost - min_cost)) * 100
            else:
                cost_score = 100
            rec['cost_score'] = round(cost_score, 2)

            if optimization_goal == 'performance':
                combined = (
                    rec['performance_score'] * 0.5
                    + rec['skill_match_score'] * 0.25
                    + rec['availability_score'] * 0.15
                    + rec['cost_score'] * 0.10
                )
            elif optimization_goal == 'cost':
                combined = (
                    rec['cost_score'] * 0.55
                    + rec['skill_match_score'] * 0.20
                    + rec['availability_score'] * 0.15
                    + rec['performance_score'] * 0.10
                )
            else:
                combined = (
                    rec['performance_score'] * 0.35
                    + rec['skill_match_score'] * 0.30
                    + rec['cost_score'] * 0.20
                    + rec['availability_score'] * 0.15
                )

            rec['combined_score'] = round(combined, 2)
            rec['reasoning'] = (
                f"Match skill {rec['skill_match_score']:.1f}, "
                f"performance {rec['performance_score']:.1f}, "
                f"availability {rec['availability_score']:.1f} (load {rec['current_load']:.1f}%), "
                f"cost score {rec['cost_score']:.1f}."
            )

        recommendations.sort(key=lambda x: x['combined_score'], reverse=True)
        return recommendations[:max_employees]

    @staticmethod
    def ai_recommendation(project, optimization_goal='balanced', rule_based_results=None):
        """Get AI explanation for ranked candidates."""
        from ai.services import AIService

        context = {
            'project_name': project.name,
            'project_description': project.description,
            'budget_for_personnel': float(project.budget_for_personnel),
            'required_departments': [dept.name for dept in project.required_departments.all()],
            'optimization_goal': optimization_goal,
            'required_skills': list(PersonnelRecommendationService.extract_required_skills(project)),
        }

        ranked_rows = []
        for row in (rule_based_results or [])[:10]:
            ranked_rows.append(
                {
                    'name': row['employee'].full_name,
                    'department': row['employee'].department.name if row['employee'].department else 'N/A',
                    'combined_score': float(row.get('combined_score', 0)),
                    'skill_match_score': float(row.get('skill_match_score', 0)),
                    'performance_score': float(row.get('performance_score', 0)),
                    'availability_score': float(row.get('availability_score', 0)),
                    'estimated_cost': float(row.get('estimated_cost', 0)),
                }
            )
        context['ranked_candidates'] = ranked_rows

        try:
            return AIService.recommend_personnel_for_project(context)
        except Exception:
            return None

    @staticmethod
    def llm_first_recommendation(project, optimization_goal='balanced', max_employees=10):
        """
        LLM-first recommendation:
        - LLM la bo chon ung vien chinh
        - scoring noi bo dung de tao candidate pool + fallback + hard constraints
        """
        from ai.services import AIService

        # Candidate pool duoc tao tu scoring de cung cap metric cho model
        candidate_pool = PersonnelRecommendationService.rule_based_recommendation(
            project,
            optimization_goal=optimization_goal,
            max_employees=max(max_employees, 8),
        )
        if not candidate_pool:
            return None

        required_skills = list(PersonnelRecommendationService.extract_required_skills(project))
        context = {
            'project_name': project.name,
            'project_description': (project.description or '')[:500],
            'budget_for_personnel': float(project.budget_for_personnel or 0),
            'optimization_goal': optimization_goal,
            'required_departments': [d.name for d in project.required_departments.all()],
            'required_skills': required_skills,
            'max_recommendations': max_employees,
            'hard_constraints': {
                'allocation_percentage_min': 10,
                'allocation_percentage_max': 100,
                'exclude_if_overallocated': True,
                'prefer_skill_match': True,
            },
            'candidate_pool': [
                {
                    'employee_id': row['employee'].id,
                    'name': row['employee'].full_name,
                    'department': row['employee'].department.name if row['employee'].department else 'N/A',
                    'skill_match_score': float(row.get('skill_match_score', 0)),
                    'performance_score': float(row.get('performance_score', 0)),
                    'availability_score': float(row.get('availability_score', 0)),
                    'current_load': float(row.get('current_load', 0)),
                    'cost_score': float(row.get('cost_score', 0)),
                    'combined_score': float(row.get('combined_score', 0)),
                    'estimated_cost_full_allocation': float(row.get('estimated_cost', 0)),
                    'estimated_hours_full_allocation': float(row.get('estimated_hours', 160)),
                }
                for row in candidate_pool
            ],
        }

        ai_pick = AIService.select_personnel_for_project(context)
        if not ai_pick:
            return None

        pool_by_id = {row['employee'].id: row for row in candidate_pool}
        recommendations = []

        for item in ai_pick.get('selected_candidates', []):
            if isinstance(item, int):
                item = {'employee_id': item}
            elif isinstance(item, str) and item.strip().isdigit():
                item = {'employee_id': int(item.strip())}
            elif not isinstance(item, dict):
                continue
            try:
                employee_id = int(item.get('employee_id'))
            except (TypeError, ValueError):
                continue

            base = pool_by_id.get(employee_id)
            if not base:
                continue

            # Hard requirement: tat ca truong chi phi/gio/% phai do AI tra ve.
            try:
                allocation_percentage = Decimal(str(item['allocation_percentage']))
                estimated_hours = Decimal(str(item['estimated_hours']))
                estimated_cost = Decimal(str(item['estimated_cost']))
            except Exception:
                continue
            allocation_percentage = max(Decimal('0'), min(Decimal('100'), allocation_percentage))
            if allocation_percentage <= 0:
                continue
            if estimated_hours <= 0:
                continue
            if estimated_cost < 0:
                continue

            # Hard constraints: tranh nhan su da qua tai
            if float(base.get('availability_score', 0)) <= 0:
                continue

            # Neu project co required skills, bo qua nguoi match qua thap
            if required_skills and float(base.get('skill_match_score', 0)) < 10:
                continue

            recommendations.append(
                {
                    'employee': base['employee'],
                    'performance_score': base.get('performance_score', 0),
                    'availability_score': base.get('availability_score', 0),
                    'current_load': base.get('current_load', 0),
                    'skill_match_score': base.get('skill_match_score', 0),
                    'cost_score': base.get('cost_score', 0),
                    'combined_score': base.get('combined_score', 0),
                    'estimated_cost': estimated_cost.quantize(Decimal('0.01')),
                    'estimated_hours': estimated_hours.quantize(Decimal('0.01')),
                    'allocation_percentage': float(allocation_percentage),
                    'reasoning': str(item.get('reasoning', '')).strip() or base.get('reasoning', ''),
                }
            )
            if len(recommendations) >= max_employees:
                break

        if not recommendations:
            return {
                'recommendations': [],
                'reasoning': str(ai_pick.get('error') or 'Model khong tra ve de xuat hop le.'),
                'total_cost': Decimal('0'),
                'method': 'llm-first-required-failed',
            }

        total_cost = sum((r['estimated_cost'] for r in recommendations), Decimal('0'))
        overall_reasoning = ai_pick.get('overall_reasoning', '').strip()
        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        reasoning = (
            f"De xuat theo che do LLM-first (model la bo chon chinh). "
            f"{overall_reasoning} (tao luc {timestamp})"
        )

        return {
            'recommendations': recommendations,
            'reasoning': reasoning,
            'total_cost': total_cost,
            'method': 'llm-first',
        }

    @staticmethod
    def recommend_personnel(project, optimization_goal='balanced', use_ai=True):
        """Recommend personnel with hard LLM-first mode when AI is enabled."""
        if use_ai:
            llm_result = PersonnelRecommendationService.llm_first_recommendation(
                project,
                optimization_goal=optimization_goal,
            )
            if llm_result and (
                llm_result.get('recommendations') or llm_result.get('method') == 'llm-first-required-failed'
            ):
                return llm_result
            # Hard LLM-first: KHONG fallback scoring khi bat AI
            return {
                'recommendations': [],
                'reasoning': (
                    'LLM-first bat buoc dang duoc kich hoat. '
                    'Model khong tra ve de xuat hop le nen he thong dung lai, khong fallback scoring.'
                ),
                'total_cost': Decimal('0'),
                'method': 'llm-first-required-failed',
            }

        # Chi dung scoring khi tat AI.
        rule_based_results = PersonnelRecommendationService.rule_based_recommendation(
            project,
            optimization_goal
        )
        total_cost = sum((r['estimated_cost'] for r in rule_based_results), Decimal('0'))
        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        reasoning = (
            f'Fallback scoring noi bo theo muc tieu {optimization_goal} '
            f'(tao luc {timestamp}).'
        )
        return {
            'recommendations': rule_based_results,
            'reasoning': reasoning,
            'total_cost': total_cost,
            'method': 'rule-based-fallback',
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



