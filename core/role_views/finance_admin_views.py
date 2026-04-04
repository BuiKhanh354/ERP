from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from budgeting.models import Budget, Expense, FinancialForecast
from core.rbac import PermissionRequiredMixin
from projects.models import Project

class FinanceAdminDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'VIEW_PROJECT_FINANCE'
    template_name = 'modules/finance_admin/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        total_budget = Budget.objects.aggregate(total=Sum('allocated_amount'))['total'] or 0
        total_spent = Expense.objects.filter(approval_status='approved').aggregate(total=Sum('amount'))['total'] or 0
        remaining_budget = total_budget - total_spent
        pending_budget_count = Budget.objects.filter(approval_status='pending').count()
        pending_expense_count = Expense.objects.filter(approval_status='pending').count()
        locked_periods = FinancialForecast.objects.values('period_year', 'period_month').distinct().count()

        # Chart: budget vs spent by project
        budget_rows = (
            Budget.objects.order_by().values('project__name')
            .annotate(total_allocated=Sum('allocated_amount'), total_spent=Sum('spent_amount'))
            .order_by('-total_allocated')[:6]
        )
        budget_vs_actual_labels = [row['project__name'][:18] for row in budget_rows]
        budget_vs_actual_budget = [float(row['total_allocated'] or 0) for row in budget_rows]
        budget_vs_actual_actual = [float(row['total_spent'] or 0) for row in budget_rows]

        # Spending trend (12 months)
        month_labels = []
        spending_trend_data = []
        base = today.replace(day=1)
        for i in range(11, -1, -1):
            month_date = base - timedelta(days=30 * i)
            month_labels.append(f"T{month_date.month}")
            month_total = (
                Expense.objects.filter(
                    approval_status='approved',
                    expense_date__year=month_date.year,
                    expense_date__month=month_date.month,
                ).aggregate(total=Sum('amount'))['total']
                or 0
            )
            spending_trend_data.append(float(month_total))

        # Expense by category (expense_type)
        category_rows = (
            Expense.objects.filter(approval_status='approved')
            .order_by()
            .values('expense_type')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        expense_type_display = dict(Expense.EXPENSE_TYPE_CHOICES)
        expense_category_labels = [expense_type_display.get(row['expense_type'], row['expense_type']) for row in category_rows]
        expense_category_data = [float(row['total'] or 0) for row in category_rows]

        # Budget utilization by project
        util_rows = []
        for row in budget_rows:
            allocated = float(row['total_allocated'] or 0)
            spent = float(row['total_spent'] or 0)
            pct = (spent / allocated * 100) if allocated > 0 else 0
            util_rows.append((row['project__name'][:18], round(min(200, pct), 2)))
        utilization_labels = [x[0] for x in util_rows]
        utilization_data = [x[1] for x in util_rows]

        pending_budgets = (
            Budget.objects.filter(approval_status='pending')
            .select_related('project', 'created_by')
            .order_by('-created_at')[:5]
        )
        pending_expenses = (
            Expense.objects.filter(approval_status='pending')
            .select_related('project', 'created_by')
            .order_by('-created_at')[:5]
        )

        context.update(
            {
                'total_budget': total_budget,
                'total_spent': total_spent,
                'remaining_budget': remaining_budget,
                'pending_budget_count': pending_budget_count,
                'pending_expense_count': pending_expense_count,
                'locked_periods': locked_periods,
                'budget_vs_actual_labels': budget_vs_actual_labels,
                'budget_vs_actual_budget': budget_vs_actual_budget,
                'budget_vs_actual_actual': budget_vs_actual_actual,
                'spending_trend_labels': month_labels,
                'spending_trend_data': spending_trend_data,
                'expense_category_labels': expense_category_labels,
                'expense_category_data': expense_category_data,
                'utilization_labels': utilization_labels,
                'utilization_data': utilization_data,
                'pending_budgets': pending_budgets,
                'pending_expenses': pending_expenses,
            }
        )
        return context


class BudgetApprovalView(PermissionRequiredMixin, TemplateView):
    permission_required = 'APPROVE_BUDGET'
    template_name = 'modules/finance_admin/pages/budget_approval.html'


class ExpenseApprovalView(PermissionRequiredMixin, TemplateView):
    permission_required = 'approve_expense'
    template_name = 'modules/finance_admin/pages/expense_approval.html'


class FinancialPeriodView(PermissionRequiredMixin, TemplateView):
    permission_required = 'LOCK_FINANCIAL_PERIOD'
    template_name = 'modules/finance_admin/pages/financial_periods.html'


class ActualCostView(PermissionRequiredMixin, TemplateView):
    permission_required = 'EDIT_ACTUAL_COST'
    template_name = 'modules/finance_admin/pages/actual_costs.html'


class FinancialReportsView(PermissionRequiredMixin, TemplateView):
    permission_required = 'view_financial_report'
    template_name = 'modules/finance_admin/pages/reports.html'
