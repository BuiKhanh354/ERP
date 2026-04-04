"""Analytics views for data visualization and insights."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

from projects.models import Project, Task
from budgeting.models import Budget, Expense
from resources.models import Employee, ResourceAllocation
from performance.models import PerformanceScore
from ai.services import AIService


class AnalyticsView(LoginRequiredMixin, TemplateView):
    """Analytics dashboard with charts and insights."""
    template_name = 'pages/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = getattr(user, 'profile', None)
        role_names = set(user.user_roles.values_list('role__name', flat=True))
        
        # Project statistics - filter theo user
        is_manager = (
            user.is_superuser
            or user.is_staff
            or bool(profile and profile.is_manager())
            or bool(role_names & {'PROJECT_MANAGER', 'HR_ADMIN', 'CFO', 'EXECUTIVE', 'RESOURCE_MANAGER'})
        )
        employee = Employee.objects.filter(user=user, is_active=True).first()
        if is_manager:
            user_projects = Project.objects.all()
        else:
            # Nhân viên chỉ xem projects được phân bổ
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                user_projects = Project.objects.filter(id__in=allocated_project_ids)
            else:
                user_projects = Project.objects.none()
        context['total_projects'] = user_projects.count()
        context['active_projects'] = user_projects.filter(status='active').count()
        context['completed_projects'] = user_projects.filter(status='completed').count()
        
        # Budget statistics - filter theo user
        if is_manager:
            budgets = Budget.objects.all()
        else:
            if employee:
                budgets = Budget.objects.filter(project_id__in=allocated_project_ids)
            else:
                budgets = Budget.objects.none()
        context['total_allocated'] = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        context['total_spent'] = budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        context['total_remaining'] = context['total_allocated'] - context['total_spent']
        context['budget_utilization'] = (context['total_spent'] / context['total_allocated'] * 100) if context['total_allocated'] > 0 else 0
        
        # Expense by type - filter theo user
        if is_manager:
            expenses = Expense.objects.all()
        else:
            if employee:
                expenses = Expense.objects.filter(project_id__in=allocated_project_ids)
            else:
                expenses = Expense.objects.none()
        expense_by_type_dict = {}
        for expense in expenses:
            expense_type = expense.get_expense_type_display()
            expense_by_type_dict[expense_type] = expense_by_type_dict.get(expense_type, 0) + float(expense.amount)
        context['expense_by_type_labels'] = list(expense_by_type_dict.keys())
        context['expense_by_type_data'] = [float(v) for v in expense_by_type_dict.values()]
        
        # Task statistics - filter theo user
        if is_manager:
            tasks = Task.objects.all()
        else:
            if employee:
                # Nhân viên chỉ xem tasks được assign cho mình
                tasks = Task.objects.filter(assigned_to=employee)
            else:
                tasks = Task.objects.none()
        context['total_tasks'] = tasks.count()
        context['completed_tasks'] = tasks.filter(status='done').count()
        context['task_completion_rate'] = (context['completed_tasks'] / context['total_tasks'] * 100) if context['total_tasks'] > 0 else 0
        
        # Employee performance - filter theo user
        if is_manager:
            employees = Employee.objects.filter(is_active=True)
        else:
            # Nhân viên chỉ xem chính mình
            if employee:
                employees = Employee.objects.filter(id=employee.id)
            else:
                employees = Employee.objects.none()
        context['total_employees'] = employees.count()
        
        # Performance scores - filter theo user
        if is_manager:
            scores = PerformanceScore.objects.all()
        else:
            if employee:
                # Nhân viên chỉ xem performance scores của chính mình
                scores = PerformanceScore.objects.filter(employee=employee)
            else:
                scores = PerformanceScore.objects.none()
        context['avg_performance'] = scores.aggregate(avg=Avg('overall_score'))['avg'] or 0
        
        # Monthly spending (last 6 months) - filter theo user
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=180)
        monthly_expenses_dict = {}
        if is_manager:
            expenses_monthly = Expense.objects.filter(expense_date__gte=start_date)
        else:
            if employee:
                expenses_monthly = Expense.objects.filter(
                    expense_date__gte=start_date,
                    project_id__in=allocated_project_ids
                )
            else:
                expenses_monthly = Expense.objects.none()
        for expense in expenses_monthly:
            month_key = expense.expense_date.strftime('%Y-%m')
            monthly_expenses_dict[month_key] = monthly_expenses_dict.get(month_key, 0) + float(expense.amount)
        sorted_monthly = dict(sorted(monthly_expenses_dict.items()))
        context['monthly_expenses_labels'] = list(sorted_monthly.keys())
        context['monthly_expenses_data'] = [float(v) for v in sorted_monthly.values()]
        
        # Project status distribution - filter theo user
        project_status_labels = []
        project_status_data = []
        for status_code, status_name in Project.STATUS_CHOICES:
            count = user_projects.filter(status=status_code).count()
            if count > 0:
                project_status_labels.append(status_name)
                project_status_data.append(count)
        context['project_status_labels'] = project_status_labels
        context['project_status_data'] = project_status_data
        
        # Budget vs Spent by Project - filter theo user
        budget_vs_spent_projects = []
        budget_vs_spent_allocated = []
        budget_vs_spent_spent = []
        projects_with_budget = user_projects.filter(budgets__isnull=False).distinct()
        for project in projects_with_budget:
            project_budgets = project.budgets.all()
            allocated = sum(b.allocated_amount for b in project_budgets)
            spent = sum(b.spent_amount for b in project_budgets)
            if allocated > 0:
                budget_vs_spent_projects.append(project.name)
                budget_vs_spent_allocated.append(float(allocated))
                budget_vs_spent_spent.append(float(spent))
        context['budget_vs_spent_projects'] = budget_vs_spent_projects
        context['budget_vs_spent_allocated'] = [float(v) for v in budget_vs_spent_allocated]
        context['budget_vs_spent_spent'] = [float(v) for v in budget_vs_spent_spent]
        
        # Project completion rates - filter theo user
        project_completion_names = []
        project_completion_rates = []
        for project in user_projects:
            tasks = project.tasks.all()
            total = tasks.count()
            completed = tasks.filter(status='done').count()
            if total > 0:
                completion_rate = (completed / total) * 100
                project_completion_names.append(project.name)
                project_completion_rates.append(completion_rate)
        context['project_completion_names'] = project_completion_names
        context['project_completion_rates'] = [float(v) for v in project_completion_rates]
        
        # Top performing employees - filter theo user
        top_employees = []
        for employee in employees:
            scores = (
                PerformanceScore.objects.filter(employee=employee)
                if is_manager
                else PerformanceScore.objects.filter(employee=employee, created_by=user)
            )
            avg_score = scores.aggregate(avg=Avg('overall_score'))['avg'] or 0
            if avg_score > 0:
                top_employees.append({
                    'name': employee.full_name,
                    'score': float(avg_score)
                })
        top_employees.sort(key=lambda x: x['score'], reverse=True)
        top_employees = top_employees[:10]  # Top 10
        context['top_employees_names'] = [emp['name'] for emp in top_employees]
        context['top_employees_scores'] = [emp['score'] for emp in top_employees]
        
        # Expense by category - filter theo user
        expense_by_category_labels = []
        expense_by_category_data = []
        expense_by_category_dict = {}
        for expense in expenses:
            category_name = expense.category.name
            expense_by_category_dict[category_name] = expense_by_category_dict.get(category_name, 0) + float(expense.amount)
        expense_by_category_labels = list(expense_by_category_dict.keys())
        expense_by_category_data = list(expense_by_category_dict.values())
        context['expense_by_category_labels'] = expense_by_category_labels
        context['expense_by_category_data'] = [float(v) for v in expense_by_category_data]
        
        return context
