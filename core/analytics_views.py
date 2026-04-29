from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Avg
from django.db import ProgrammingError, OperationalError
from django.utils import timezone
from datetime import timedelta

from projects.models import Project, Task
from budgeting.models import Budget, Expense
from resources.models import Employee, ResourceAllocation
from performance.models import PerformanceScore


class AnalyticsView(LoginRequiredMixin, TemplateView):
    """Analytics dashboard with charts and insights."""

    template_name = 'pages/analytics.html'

    def _safe_performance_avg(self, qs):
        try:
            return qs.aggregate(avg=Avg('overall_score'))['avg'] or 0
        except (ProgrammingError, OperationalError):
            return 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role_names = set(user.user_roles.values_list('role__name', flat=True))

        is_manager = (
            user.is_superuser
            or user.is_staff
            or bool(role_names & {'ADMIN', 'MANAGER', 'FINANCE'})
        )
        employee = Employee.objects.filter(user=user, is_active=True).first()

        allocated_project_ids = []
        if employee:
            allocated_project_ids = list(
                ResourceAllocation.objects.filter(employee=employee)
                .values_list('project_id', flat=True)
                .distinct()
            )

        # Projects scope
        if is_manager:
            user_projects = Project.objects.all()
        else:
            user_projects = Project.objects.filter(id__in=allocated_project_ids) if employee else Project.objects.none()

        context['total_projects'] = user_projects.count()
        context['active_projects'] = user_projects.filter(status='active').count()
        context['completed_projects'] = user_projects.filter(status='completed').count()

        # Budgets scope
        if is_manager:
            budgets = Budget.objects.all()
        else:
            budgets = Budget.objects.filter(project_id__in=allocated_project_ids) if employee else Budget.objects.none()

        context['total_allocated'] = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        context['total_spent'] = budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        context['total_remaining'] = context['total_allocated'] - context['total_spent']
        context['budget_utilization'] = (
            (context['total_spent'] / context['total_allocated'] * 100)
            if context['total_allocated'] > 0 else 0
        )

        # Expenses scope
        if is_manager:
            expenses = Expense.objects.all()
        else:
            expenses = Expense.objects.filter(project_id__in=allocated_project_ids) if employee else Expense.objects.none()

        expense_by_type = {}
        for expense in expenses:
            key = expense.get_expense_type_display()
            expense_by_type[key] = expense_by_type.get(key, 0) + float(expense.amount)
        context['expense_by_type_labels'] = list(expense_by_type.keys())
        context['expense_by_type_data'] = [float(v) for v in expense_by_type.values()]

        # Tasks scope
        if is_manager:
            tasks = Task.objects.all()
        else:
            tasks = Task.objects.filter(assigned_to=employee) if employee else Task.objects.none()

        context['total_tasks'] = tasks.count()
        context['completed_tasks'] = tasks.filter(status='done').count()
        context['task_completion_rate'] = (
            (context['completed_tasks'] / context['total_tasks'] * 100)
            if context['total_tasks'] > 0 else 0
        )

        # Employees scope
        if is_manager:
            employees = Employee.objects.filter(is_active=True)
        else:
            employees = Employee.objects.filter(id=employee.id) if employee else Employee.objects.none()
        context['total_employees'] = employees.count()

        # Performance safe handling
        performance_table_available = True
        try:
            if is_manager:
                score_qs = PerformanceScore.objects.all()
            else:
                score_qs = PerformanceScore.objects.filter(employee=employee) if employee else PerformanceScore.objects.none()
            context['avg_performance'] = score_qs.aggregate(avg=Avg('overall_score'))['avg'] or 0
        except (ProgrammingError, OperationalError):
            performance_table_available = False
            context['avg_performance'] = 0

        # Monthly spending (last 6 months)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=180)
        if is_manager:
            expenses_monthly = Expense.objects.filter(expense_date__gte=start_date)
        else:
            expenses_monthly = Expense.objects.filter(
                expense_date__gte=start_date,
                project_id__in=allocated_project_ids,
            ) if employee else Expense.objects.none()

        monthly_expenses = {}
        for expense in expenses_monthly:
            month_key = expense.expense_date.strftime('%Y-%m')
            monthly_expenses[month_key] = monthly_expenses.get(month_key, 0) + float(expense.amount)
        monthly_expenses = dict(sorted(monthly_expenses.items()))
        context['monthly_expenses_labels'] = list(monthly_expenses.keys())
        context['monthly_expenses_data'] = [float(v) for v in monthly_expenses.values()]

        # Project status distribution
        labels, values = [], []
        for status_code, status_name in Project.STATUS_CHOICES:
            c = user_projects.filter(status=status_code).count()
            if c > 0:
                labels.append(status_name)
                values.append(c)
        context['project_status_labels'] = labels
        context['project_status_data'] = values

        # Budget vs spent per project
        p_names, p_alloc, p_spent = [], [], []
        for project in user_projects.filter(budgets__isnull=False).distinct():
            project_budgets = project.budgets.all()
            allocated = sum(b.allocated_amount for b in project_budgets)
            spent = sum(b.spent_amount for b in project_budgets)
            if allocated > 0:
                p_names.append(project.name)
                p_alloc.append(float(allocated))
                p_spent.append(float(spent))
        context['budget_vs_spent_projects'] = p_names
        context['budget_vs_spent_allocated'] = p_alloc
        context['budget_vs_spent_spent'] = p_spent

        # Project completion rates
        completion_names, completion_rates = [], []
        for project in user_projects:
            p_tasks = project.tasks.all()
            total = p_tasks.count()
            done = p_tasks.filter(status='done').count()
            if total > 0:
                completion_names.append(project.name)
                completion_rates.append((done / total) * 100)
        context['project_completion_names'] = completion_names
        context['project_completion_rates'] = [float(v) for v in completion_rates]

        # Top employees: PerformanceScore if available, else KPI fallback
        top_employees = []
        for emp in employees:
            avg_score = 0
            if performance_table_available:
                try:
                    emp_qs = PerformanceScore.objects.filter(employee=emp)
                    if not is_manager:
                        emp_qs = emp_qs.filter(created_by=user)
                    avg_score = emp_qs.aggregate(avg=Avg('overall_score'))['avg'] or 0
                except (ProgrammingError, OperationalError):
                    avg_score = 0
            if avg_score <= 0:
                avg_score = float(emp.kpi_current or 0)
            if avg_score > 0:
                top_employees.append({'name': emp.full_name, 'score': float(avg_score)})

        top_employees.sort(key=lambda x: x['score'], reverse=True)
        top_employees = top_employees[:10]
        context['top_employees_names'] = [e['name'] for e in top_employees]
        context['top_employees_scores'] = [e['score'] for e in top_employees]

        # Expense by category
        expense_by_category = {}
        for expense in expenses:
            name = expense.category.name
            expense_by_category[name] = expense_by_category.get(name, 0) + float(expense.amount)
        context['expense_by_category_labels'] = list(expense_by_category.keys())
        context['expense_by_category_data'] = [float(v) for v in expense_by_category.values()]

        return context
