"""Service layer for the Accounting module."""
import json
from decimal import Decimal
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta

from .models import Invoice, Payment
from budgeting.models import Budget, Expense, BudgetCategory
from projects.models import Project


class AccountingDashboardService:
    """Aggregate data for the accounting dashboard."""

    @staticmethod
    def get_dashboard_data():
        """Return all data needed for the accounting dashboard."""
        today = timezone.now().date()

        # --- Widget data ---
        total_revenue = Invoice.objects.filter(
            status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        total_expenses = Expense.objects.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        profit_loss = total_revenue - total_expenses

        pending_invoices = Invoice.objects.filter(
            status__in=['draft', 'sent']
        ).count()

        overdue_invoices = Invoice.objects.filter(
            status__in=['draft', 'sent'], due_date__lt=today
        ).count()

        # --- Chart data: Revenue by Project ---
        revenue_by_project_qs = Invoice.objects.filter(
            status='paid'
        ).values('project__name').annotate(
            total=Sum('total_amount')
        ).order_by('-total')[:10]

        revenue_by_project = {
            'labels': [r['project__name'] for r in revenue_by_project_qs],
            'data': [float(r['total']) for r in revenue_by_project_qs],
        }

        # --- Chart data: Expenses by Category ---
        expenses_by_category_qs = Expense.objects.values(
            'category__name'
        ).annotate(
            total=Sum('amount')
        ).order_by('-total')[:10]

        expenses_by_category = {
            'labels': [e['category__name'] for e in expenses_by_category_qs],
            'data': [float(e['total']) for e in expenses_by_category_qs],
        }

        # --- Chart data: Monthly Cash Flow (last 12 months) ---
        months = []
        revenue_monthly = []
        expense_monthly = []
        for i in range(11, -1, -1):
            dt = today - timedelta(days=i * 30)
            month_start = dt.replace(day=1)
            if dt.month == 12:
                month_end = dt.replace(year=dt.year + 1, month=1, day=1)
            else:
                month_end = dt.replace(month=dt.month + 1, day=1)

            month_label = month_start.strftime('%m/%Y')
            months.append(month_label)

            rev = Invoice.objects.filter(
                status='paid',
                issue_date__gte=month_start,
                issue_date__lt=month_end,
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            exp = Expense.objects.filter(
                expense_date__gte=month_start,
                expense_date__lt=month_end,
            ).aggregate(total=Sum('amount'))['total'] or 0

            revenue_monthly.append(float(rev))
            expense_monthly.append(float(exp))

        monthly_cash_flow = {
            'labels': months,
            'revenue': revenue_monthly,
            'expenses': expense_monthly,
        }

        # --- Table data: Recent Payments ---
        recent_payments = Payment.objects.select_related(
            'invoice', 'invoice__client', 'invoice__project'
        ).order_by('-payment_date')[:10]

        # --- Table data: Recent Expenses ---
        recent_expenses = Expense.objects.select_related(
            'project', 'category'
        ).order_by('-expense_date')[:10]

        return {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'profit_loss': profit_loss,
            'pending_invoices': pending_invoices,
            'overdue_invoices': overdue_invoices,
            'revenue_by_project': json.dumps(revenue_by_project),
            'expenses_by_category': json.dumps(expenses_by_category),
            'monthly_cash_flow': json.dumps(monthly_cash_flow),
            'recent_payments': recent_payments,
            'recent_expenses': recent_expenses,
        }


class ReportService:
    """Generate financial reports."""

    @staticmethod
    def project_profit_loss(project_id=None, date_from=None, date_to=None):
        """Project Profit/Loss Report."""
        projects = Project.objects.all()
        if project_id:
            projects = projects.filter(id=project_id)

        report_data = []
        for project in projects:
            inv_filter = Q(project=project, status='paid')
            exp_filter = Q(project=project)
            if date_from:
                inv_filter &= Q(issue_date__gte=date_from)
                exp_filter &= Q(expense_date__gte=date_from)
            if date_to:
                inv_filter &= Q(issue_date__lte=date_to)
                exp_filter &= Q(expense_date__lte=date_to)

            revenue = Invoice.objects.filter(inv_filter).aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0')
            expenses = Expense.objects.filter(exp_filter).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')

            report_data.append({
                'project': project.name,
                'revenue': revenue,
                'expenses': expenses,
                'profit_loss': revenue - expenses,
            })

        return report_data

    @staticmethod
    def monthly_revenue(date_from=None, date_to=None):
        """Monthly Revenue Report."""
        qs = Invoice.objects.filter(status='paid')
        if date_from:
            qs = qs.filter(issue_date__gte=date_from)
        if date_to:
            qs = qs.filter(issue_date__lte=date_to)

        result = qs.extra(
            select={'month': "FORMAT(issue_date, 'yyyy-MM')"}
        ).values('month').annotate(
            total=Sum('total_amount'),
            count=Count('id'),
        ).order_by('month')

        return list(result)

    @staticmethod
    def expense_by_category(date_from=None, date_to=None):
        """Expense Report by Category."""
        qs = Expense.objects.all()
        if date_from:
            qs = qs.filter(expense_date__gte=date_from)
        if date_to:
            qs = qs.filter(expense_date__lte=date_to)

        result = qs.values('category__name').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total')

        return list(result)

    @staticmethod
    def cash_flow(date_from=None, date_to=None):
        """Cash Flow Report."""
        inv_qs = Invoice.objects.filter(status='paid')
        exp_qs = Expense.objects.all()
        if date_from:
            inv_qs = inv_qs.filter(issue_date__gte=date_from)
            exp_qs = exp_qs.filter(expense_date__gte=date_from)
        if date_to:
            inv_qs = inv_qs.filter(issue_date__lte=date_to)
            exp_qs = exp_qs.filter(expense_date__lte=date_to)

        revenue_by_month = inv_qs.extra(
            select={'month': "FORMAT(issue_date, 'yyyy-MM')"}
        ).values('month').annotate(total=Sum('total_amount')).order_by('month')

        expense_by_month = exp_qs.extra(
            select={'month': "FORMAT(expense_date, 'yyyy-MM')"}
        ).values('month').annotate(total=Sum('amount')).order_by('month')

        # Merge into a single timeline
        months_set = set()
        rev_map = {}
        exp_map = {}
        for r in revenue_by_month:
            months_set.add(r['month'])
            rev_map[r['month']] = float(r['total'])
        for e in expense_by_month:
            months_set.add(e['month'])
            exp_map[e['month']] = float(e['total'])

        data = []
        for m in sorted(months_set):
            rev = rev_map.get(m, 0)
            exp = exp_map.get(m, 0)
            data.append({
                'month': m,
                'revenue': rev,
                'expenses': exp,
                'net_cash_flow': rev - exp,
            })

        return data
