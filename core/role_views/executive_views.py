from datetime import timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView

from budgeting.models import Expense, FinancialForecast
from core.rbac import PermissionRequiredMixin
from projects.models import Project, Task
from resources.models import Employee

class ExecutiveDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_COMPANY_DASHBOARD'
    template_name = 'modules/executive/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        year_start = today.replace(month=1, day=1)

        active_projects = Project.objects.filter(status='active').count()
        revenue_ytd = (
            FinancialForecast.objects.filter(
                forecast_type='revenue',
                period_year=today.year,
                period_month__lte=today.month,
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        expense_ytd = (
            Expense.objects.filter(
                approval_status='approved',
                expense_date__gte=year_start,
                expense_date__lte=today,
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        net_profit = revenue_ytd - expense_ytd
        total_employees = Employee.objects.filter(is_active=True).count()
        avg_progress = Task.objects.aggregate(avg=Avg('progress_percent'))['avg'] or 0

        # Revenue trend (last 12 months from forecast table)
        month_keys = []
        month_labels = []
        base = today.replace(day=1)
        for i in range(11, -1, -1):
            d = (base - timedelta(days=30 * i))
            month_keys.append((d.year, d.month))
            month_labels.append(f"T{d.month}")

        revenue_map = {
            (row['period_year'], row['period_month']): float(row['amount'])
            for row in FinancialForecast.objects.filter(
                forecast_type='revenue'
            ).values('period_year', 'period_month', 'amount')
        }
        revenue_trend_data = [round(revenue_map.get(key, 0.0), 2) for key in month_keys]

        # Project profit view
        top_profit_projects = []
        for p in Project.objects.all().order_by('-created_at')[:10]:
            revenue = float(p.estimated_budget or 0)
            cost = float(p.actual_budget or 0)
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0
            top_profit_projects.append(
                {
                    'name': p.name,
                    'revenue': revenue,
                    'cost': cost,
                    'profit': profit,
                    'margin': margin,
                }
            )
        top_profit_projects.sort(key=lambda x: x['profit'], reverse=True)
        top_profit_projects = top_profit_projects[:5]

        # Status distribution
        status_qs = Project.objects.order_by().values('status').annotate(count=Count('id'))
        status_map = {row['status']: row['count'] for row in status_qs}
        project_status_labels = ['Planning', 'Active', 'On Hold', 'Completed', 'Cancelled']
        project_status_data = [
            status_map.get('planning', 0),
            status_map.get('active', 0),
            status_map.get('on_hold', 0),
            status_map.get('completed', 0),
            status_map.get('cancelled', 0),
        ]

        # Budget vs actual chart
        bv_rows = Project.objects.order_by('-created_at')[:6]
        budget_vs_actual_labels = [p.name[:18] for p in bv_rows]
        budget_vs_actual_budget = [float(p.estimated_budget or 0) for p in bv_rows]
        budget_vs_actual_actual = [float(p.actual_budget or 0) for p in bv_rows]

        # Risky projects
        risky_projects = []
        near_deadline = today + timedelta(days=14)
        for p in Project.objects.filter(
            Q(actual_budget__gt=F('estimated_budget')) |
            Q(end_date__isnull=False, end_date__lte=near_deadline, status__in=['planning', 'active', 'on_hold'])
        ).order_by('-created_at')[:5]:
            progress = float(p.calculated_progress or 0)
            issue = 'Vượt ngân sách' if (p.actual_budget or 0) > (p.estimated_budget or 0) else 'Sắp tới hạn'
            risky_projects.append(
                {
                    'name': p.name,
                    'issue': issue,
                    'progress': progress,
                    'budget_ratio': (float(p.actual_budget or 0) / float(p.estimated_budget or 1)) * 100 if (p.estimated_budget or 0) else 0,
                }
            )

        context.update(
            {
                'active_projects': active_projects,
                'revenue_ytd': revenue_ytd,
                'expense_ytd': expense_ytd,
                'net_profit': net_profit,
                'total_employees': total_employees,
                'avg_progress': round(float(avg_progress), 2),
                'revenue_trend_labels': month_labels,
                'revenue_trend_data': revenue_trend_data,
                'profit_by_project_labels': [p['name'][:18] for p in top_profit_projects],
                'profit_by_project_data': [round(p['profit'], 2) for p in top_profit_projects],
                'project_status_labels': project_status_labels,
                'project_status_data': project_status_data,
                'budget_vs_actual_labels': budget_vs_actual_labels,
                'budget_vs_actual_budget': budget_vs_actual_budget,
                'budget_vs_actual_actual': budget_vs_actual_actual,
                'top_profit_projects': top_profit_projects,
                'risky_projects': risky_projects,
            }
        )
        return context


class ExecutiveProjectPortfolioView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_ALL_PROJECTS'
    template_name = 'modules/executive/pages/project_portfolio.html'


class ExecutiveFinancialReportsView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_financial_report'
    template_name = 'modules/executive/pages/financial_reports.html'


class ExecutivePerformanceView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_performance'
    template_name = 'modules/executive/pages/performance.html'
