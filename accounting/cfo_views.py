"""
CFO (Giám đốc Tài chính) web views.

Tất cả views chỉ sử dụng model & permission đã có trong hệ thống.
"""
import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum, Q, F, Count, Case, When, Value, DecimalField
from django.db.models.functions import TruncMonth, Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, ListView, DetailView, View

from core.rbac import PermissionRequiredMixin
from accounting.models import Invoice, Payment, VendorBill, VendorPayment
from budgeting.models import Budget, Expense, BudgetCategory, FinancialForecast
from projects.models import Project
from resources.models import Department


# ===================================================================
# CFO Dashboard
# ===================================================================

class CFODashboardView(PermissionRequiredMixin, TemplateView):
    """CFO strategic financial dashboard."""
    template_name = 'cfo/dashboard.html'
    permission_required = 'VIEW_PROJECT_FINANCE'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        # --- KPI Cards ---
        total_revenue = Invoice.objects.filter(
            status__in=['sent', 'paid']
        ).aggregate(total=Coalesce(Sum('total_amount'), Decimal('0')))['total']

        total_cost = Expense.objects.filter(
            approval_status='approved'
        ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']

        net_profit = total_revenue - total_cost

        # EBITDA = Net Profit + Interest + Taxes + Depreciation
        interest = Expense.objects.filter(approval_status='approved', category__expense_class='INTEREST').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        taxes = Expense.objects.filter(approval_status='approved', category__expense_class='TAX').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        depreciation = Expense.objects.filter(approval_status='approved', category__expense_class='DEPRECIATION').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        ebitda = net_profit + interest + taxes + depreciation

        total_payments_in = Payment.objects.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']
        total_payments_out = VendorPayment.objects.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']
        cash_balance = total_payments_in - total_payments_out

        operating_margin = (
            (net_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0')
        )

        context['total_revenue'] = total_revenue
        context['total_cost'] = total_cost
        context['net_profit'] = net_profit
        context['ebitda'] = ebitda
        context['cash_balance'] = cash_balance
        context['operating_margin'] = round(operating_margin, 1)

        # Revenue by Region
        region_rev = Invoice.objects.values('region').annotate(total=Sum('total_amount')).order_by('-total')
        context['revenue_by_region_json'] = json.dumps({
            'labels': [dict(Invoice.REGION_CHOICES).get(r['region'], r['region']) for r in region_rev],
            'data': [float(r['total']) for r in region_rev],
        })

        # P&L Summary
        cogs = Expense.objects.filter(approval_status='approved', category__expense_class='COGS').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        opex = Expense.objects.filter(approval_status='approved', category__expense_class='OPEX').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        gross_profit = total_revenue - cogs
        context['pnl_summary'] = {
            'revenue': total_revenue,
            'cogs': cogs,
            'gross_profit': gross_profit,
            'opex': opex,
            'ebitda': ebitda,
            'net_profit': net_profit,
        }

        # --- Revenue Trend (last 12 months) ---
        revenue_by_month = list(
            Invoice.objects.filter(status='paid')
            .annotate(month=TruncMonth('issue_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )[-12:]
        context['revenue_trend_json'] = json.dumps({
            'labels': [r['month'].strftime('%m/%Y') for r in revenue_by_month],
            'data': [float(r['total']) for r in revenue_by_month],
        })

        # --- Profit Trend (last 12 months) ---
        expense_by_month = list(
            Expense.objects.filter(approval_status='approved')
            .annotate(month=TruncMonth('expense_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )[-12:]
        expense_map = {e['month']: float(e['total']) for e in expense_by_month}
        profit_labels = []
        profit_data = []
        for r in revenue_by_month:
            profit_labels.append(r['month'].strftime('%m/%Y'))
            rev = float(r['total'])
            exp = expense_map.get(r['month'], 0)
            profit_data.append(rev - exp)
        context['profit_trend_json'] = json.dumps({
            'labels': profit_labels,
            'data': profit_data,
        })

        # --- Cash Flow Forecast (by month) ---
        payment_in_by_month = list(
            Payment.objects.annotate(month=TruncMonth('payment_date'))
            .values('month').annotate(total=Sum('amount')).order_by('month')
        )[-12:]
        payment_out_by_month = list(
            VendorPayment.objects.annotate(month=TruncMonth('payment_date'))
            .values('month').annotate(total=Sum('amount')).order_by('month')
        )[-12:]
        
        all_months = sorted(set([p['month'] for p in payment_in_by_month] + [p['month'] for p in payment_out_by_month]))
        inflow_map = {p['month']: float(p['total']) for p in payment_in_by_month}
        outflow_map = {p['month']: float(p['total']) for p in payment_out_by_month}

        cf_labels = []
        cf_inflow = []
        cf_outflow = []
        cf_net = []
        for m in all_months:
            cf_labels.append(m.strftime('%m/%Y'))
            infl = inflow_map.get(m, 0)
            outfl = outflow_map.get(m, 0)
            cf_inflow.append(infl)
            cf_outflow.append(outfl)
            cf_net.append(infl - outfl)
            
        context['cash_flow_json'] = json.dumps({
            'labels': cf_labels,
            'inflow': cf_inflow,
            'outflow': cf_outflow,
            'net': cf_net,
        })

        # --- Expense Breakdown (by type) ---
        expense_by_type = (
            Expense.objects.filter(approval_status='approved')
            .values('expense_type')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        type_map = dict(Expense.EXPENSE_TYPE_CHOICES)
        context['expense_breakdown_json'] = json.dumps({
            'labels': [type_map.get(e['expense_type'], e['expense_type']) for e in expense_by_type],
            'data': [float(e['total']) for e in expense_by_type],
        })

        # --- Profit by Project ---
        projects = Project.objects.all()
        proj_profit_labels = []
        proj_profit_data = []
        for p in projects:
            rev = Invoice.objects.filter(
                project=p, status='paid'
            ).aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
            cost = Expense.objects.filter(
                project=p, approval_status='approved'
            ).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
            profit = float(rev - cost)
            proj_profit_labels.append(p.name)
            proj_profit_data.append(profit)
        # Sort by profit descending
        paired = sorted(zip(proj_profit_labels, proj_profit_data), key=lambda x: x[1], reverse=True)
        if paired:
            proj_profit_labels, proj_profit_data = zip(*paired)
        context['profit_by_project_json'] = json.dumps({
            'labels': list(proj_profit_labels),
            'data': list(proj_profit_data),
        })

        # --- Budget vs Actual ---
        budget_vs_actual = (
            Budget.objects.filter(approval_status='approved')
            .values('project__name')
            .annotate(
                total_budget=Sum('allocated_amount'),
                total_spent=Sum('spent_amount'),
            )
            .order_by('project__name')
        )
        context['budget_vs_actual_json'] = json.dumps({
            'labels': [b['project__name'] for b in budget_vs_actual],
            'budget': [float(b['total_budget']) for b in budget_vs_actual],
            'actual': [float(b['total_spent']) for b in budget_vs_actual],
        })

        # --- Tables ---
        # Top Profitable Projects
        project_financials = []
        for p in projects:
            rev = Invoice.objects.filter(
                project=p, status='paid'
            ).aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
            cost = Expense.objects.filter(
                project=p, approval_status='approved'
            ).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
            profit = rev - cost
            margin = (profit / rev * 100) if rev > 0 else Decimal('0')
            project_financials.append({
                'project': p,
                'revenue': rev,
                'cost': cost,
                'profit': profit,
                'margin': round(margin, 1),
            })
        project_financials.sort(key=lambda x: x['profit'], reverse=True)
        context['top_profitable'] = project_financials[:5]

        # High Risk Projects (budget utilization > 80% or negative profit)
        high_risk = [pf for pf in project_financials if pf['profit'] < 0 or pf['margin'] < 5]
        context['high_risk_projects'] = high_risk[:5]

        # AR & AP
        context['accounts_receivable'] = Invoice.objects.exclude(status='paid').annotate(
            is_overdue=Case(When(due_date__lt=today, then=Value(True)), default=Value(False))
        ).select_related('client').order_by('due_date')[:10]

        context['accounts_payable'] = VendorBill.objects.exclude(status='paid').annotate(
            is_overdue=Case(When(due_date__lt=today, then=Value(True)), default=Value(False))
        ).order_by('due_date')[:10]

        # Financial Forecasts
        context['forecasts'] = FinancialForecast.objects.filter(period_year__gte=today.year).order_by('period_year', 'period_month')[:6]

        # Budget Alerts (utilization > 80%)
        budget_alerts = []
        for b in Budget.objects.filter(approval_status='approved').select_related('project', 'category'):
            if b.allocated_amount > 0 and b.utilization_percentage > 80:
                budget_alerts.append(b)
        context['budget_alerts'] = budget_alerts[:10]

        # Pending approval counts for badge
        context['pending_expense_count'] = Expense.objects.filter(approval_status='pending').count()
        context['pending_budget_count'] = Budget.objects.filter(approval_status='pending').count()

        return context


# ===================================================================
# Project Finance
# ===================================================================

class ProjectFinanceView(PermissionRequiredMixin, ListView):
    """Financial performance by project."""
    template_name = 'cfo/project_finance.html'
    context_object_name = 'project_financials'
    permission_required = 'VIEW_PROJECT_FINANCE'

    def get_queryset(self):
        projects = Project.objects.all().order_by('name')
        status = self.request.GET.get('status')
        if status:
            projects = projects.filter(status=status)

        financials = []
        for p in projects:
            budget = Budget.objects.filter(
                project=p, approval_status='approved'
            ).aggregate(t=Coalesce(Sum('allocated_amount'), Decimal('0')))['t']
            cost = Expense.objects.filter(
                project=p, approval_status='approved'
            ).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
            revenue = Invoice.objects.filter(
                project=p, status='paid'
            ).aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else Decimal('0')
            financials.append({
                'project': p,
                'budget': budget,
                'cost': cost,
                'revenue': revenue,
                'profit': profit,
                'margin': round(margin, 1),
            })

        sort_by = self.request.GET.get('sort', 'profit')
        reverse = self.request.GET.get('order', 'desc') == 'desc'
        if sort_by in ('budget', 'cost', 'revenue', 'profit', 'margin'):
            financials.sort(key=lambda x: x[sort_by], reverse=reverse)
        return financials

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Project.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', 'profit')
        context['current_order'] = self.request.GET.get('order', 'desc')
        return context


class ProjectFinanceDetailView(PermissionRequiredMixin, DetailView):
    """Financial detail for a single project."""
    model = Project
    template_name = 'cfo/project_finance_detail.html'
    context_object_name = 'project'
    permission_required = 'VIEW_PROJECT_FINANCE'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        p = self.object

        # KPI
        budget = Budget.objects.filter(
            project=p, approval_status='approved'
        ).aggregate(t=Coalesce(Sum('allocated_amount'), Decimal('0')))['t']
        cost = Expense.objects.filter(
            project=p, approval_status='approved'
        ).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
        revenue = Invoice.objects.filter(
            project=p, status='paid'
        ).aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue > 0 else Decimal('0')

        context['budget_total'] = budget
        context['cost_total'] = cost
        context['revenue_total'] = revenue
        context['profit_total'] = profit
        context['margin_pct'] = round(margin, 1)

        # Lists
        context['invoices'] = Invoice.objects.filter(
            project=p
        ).select_related('client').order_by('-issue_date')
        context['expenses'] = Expense.objects.filter(
            project=p
        ).select_related('category').order_by('-expense_date')
        context['budgets'] = Budget.objects.filter(
            project=p
        ).select_related('category').order_by('category__name')

        # Revenue vs Cost timeline chart
        rev_by_month = (
            Invoice.objects.filter(project=p, status='paid')
            .annotate(month=TruncMonth('issue_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )
        cost_by_month = (
            Expense.objects.filter(project=p, approval_status='approved')
            .annotate(month=TruncMonth('expense_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        # Merge months
        all_months = sorted(set(
            [r['month'] for r in rev_by_month] +
            [c['month'] for c in cost_by_month]
        ))
        rev_map = {r['month']: float(r['total']) for r in rev_by_month}
        cost_map = {c['month']: float(c['total']) for c in cost_by_month}
        context['timeline_json'] = json.dumps({
            'labels': [m.strftime('%m/%Y') for m in all_months],
            'revenue': [rev_map.get(m, 0) for m in all_months],
            'cost': [cost_map.get(m, 0) for m in all_months],
        })

        return context


# ===================================================================
# Budget Monitoring
# ===================================================================

class BudgetMonitoringView(PermissionRequiredMixin, TemplateView):
    """Budget vs Actual monitoring with approve/reject."""
    template_name = 'cfo/budget_monitoring.html'
    permission_required = 'APPROVE_BUDGET'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Budget by project
        budget_by_project = (
            Budget.objects.filter(approval_status='approved')
            .values('project__id', 'project__name')
            .annotate(
                total_allocated=Sum('allocated_amount'),
                total_spent=Sum('spent_amount'),
            )
            .order_by('project__name')
        )
        for bp in budget_by_project:
            bp['remaining'] = bp['total_allocated'] - bp['total_spent']
            bp['utilization'] = (
                round(bp['total_spent'] / bp['total_allocated'] * 100, 1)
                if bp['total_allocated'] > 0 else 0
            )
        context['budget_by_project'] = budget_by_project

        # Budget by department (via project departments)
        dept_budgets = defaultdict(lambda: {'allocated': Decimal('0'), 'spent': Decimal('0')})
        for b in Budget.objects.filter(approval_status='approved').select_related('project'):
            for dept in b.project.departments.all():
                dept_budgets[dept.name]['allocated'] += b.allocated_amount
                dept_budgets[dept.name]['spent'] += b.spent_amount
        dept_list = []
        for name, vals in dept_budgets.items():
            remaining = vals['allocated'] - vals['spent']
            utilization = (
                round(float(vals['spent'] / vals['allocated'] * 100), 1)
                if vals['allocated'] > 0 else 0
            )
            dept_list.append({
                'name': name,
                'allocated': vals['allocated'],
                'spent': vals['spent'],
                'remaining': remaining,
                'utilization': utilization,
            })
        dept_list.sort(key=lambda x: x['name'])
        context['budget_by_department'] = dept_list

        # Pending budgets
        context['pending_budgets'] = Budget.objects.filter(
            approval_status='pending'
        ).select_related('project', 'category').order_by('-created_at')

        # Chart data
        context['budget_chart_json'] = json.dumps({
            'labels': [b['project__name'] for b in budget_by_project],
            'budget': [float(b['total_allocated']) for b in budget_by_project],
            'actual': [float(b['total_spent']) for b in budget_by_project],
        })

        return context


# ===================================================================
# Approval Center
# ===================================================================

class ApprovalCenterView(PermissionRequiredMixin, TemplateView):
    """Central approval hub for expenses and budgets."""
    template_name = 'cfo/approval_center.html'
    permission_required = 'approve_expense'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_expenses'] = Expense.objects.filter(
            approval_status='pending'
        ).select_related('project', 'category').order_by('-expense_date')
        context['pending_budgets'] = Budget.objects.filter(
            approval_status='pending'
        ).select_related('project', 'category').order_by('-created_at')
        context['pending_expense_count'] = context['pending_expenses'].count()
        context['pending_budget_count'] = context['pending_budgets'].count()
        return context


class ApproveExpenseView(PermissionRequiredMixin, View):
    """Approve a pending expense."""
    permission_required = 'approve_expense'

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, approval_status='pending')
        expense.approval_status = 'approved'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
        messages.success(request, f'Đã phê duyệt chi phí #{pk}.')
        return redirect('cfo:approval_center')


class RejectExpenseView(PermissionRequiredMixin, View):
    """Reject a pending expense."""
    permission_required = 'approve_expense'

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, approval_status='pending')
        expense.approval_status = 'rejected'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
        messages.success(request, f'Đã từ chối chi phí #{pk}.')
        return redirect('cfo:approval_center')


class ApproveBudgetActionView(PermissionRequiredMixin, View):
    """Approve a pending budget."""
    permission_required = 'APPROVE_BUDGET'

    def post(self, request, pk):
        budget = get_object_or_404(Budget, pk=pk, approval_status='pending')
        budget.approval_status = 'approved'
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
        messages.success(request, f'Đã phê duyệt ngân sách #{pk}.')
        return redirect('cfo:approval_center')


class RejectBudgetView(PermissionRequiredMixin, View):
    """Reject a pending budget."""
    permission_required = 'APPROVE_BUDGET'

    def post(self, request, pk):
        budget = get_object_or_404(Budget, pk=pk, approval_status='pending')
        budget.approval_status = 'rejected'
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
        messages.success(request, f'Đã từ chối ngân sách #{pk}.')
        return redirect('cfo:approval_center')


# ===================================================================
# Financial Reports
# ===================================================================

class FinancialReportsView(PermissionRequiredMixin, TemplateView):
    """Financial reports with filters and CSV export."""
    template_name = 'cfo/reports.html'
    permission_required = 'view_financial_report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all().order_by('name')
        context['departments'] = Department.objects.all().order_by('name')

        # Parse filters
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        project_id = self.request.GET.get('project')
        context['current_date_from'] = date_from or ''
        context['current_date_to'] = date_to or ''
        context['current_project'] = project_id or ''

        # Build filter kwargs
        inv_filter = Q(status='paid')
        exp_filter = Q(approval_status='approved')
        if date_from:
            inv_filter &= Q(issue_date__gte=date_from)
            exp_filter &= Q(expense_date__gte=date_from)
        if date_to:
            inv_filter &= Q(issue_date__lte=date_to)
            exp_filter &= Q(expense_date__lte=date_to)
        if project_id:
            inv_filter &= Q(project_id=project_id)
            exp_filter &= Q(project_id=project_id)

        # Profit & Loss
        pl_data = []
        projects_qs = Project.objects.all().order_by('name')
        if project_id:
            projects_qs = projects_qs.filter(id=project_id)
        for p in projects_qs:
            rev = Invoice.objects.filter(
                inv_filter, project=p
            ).aggregate(t=Coalesce(Sum('total_amount'), Decimal('0')))['t']
            cost = Expense.objects.filter(
                exp_filter, project=p
            ).aggregate(t=Coalesce(Sum('amount'), Decimal('0')))['t']
            pl_data.append({
                'project': p.name,
                'revenue': rev,
                'cost': cost,
                'profit': rev - cost,
            })
        context['pl_data'] = pl_data
        context['pl_total_revenue'] = sum(d['revenue'] for d in pl_data)
        context['pl_total_cost'] = sum(d['cost'] for d in pl_data)
        context['pl_total_profit'] = sum(d['profit'] for d in pl_data)

        # Cash Flow (monthly)
        cash_flow = []
        rev_months = (
            Invoice.objects.filter(inv_filter)
            .annotate(month=TruncMonth('issue_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )
        exp_months = (
            Expense.objects.filter(exp_filter)
            .annotate(month=TruncMonth('expense_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        all_months = sorted(set(
            [r['month'] for r in rev_months] +
            [e['month'] for e in exp_months]
        ))
        rev_m = {r['month']: r['total'] for r in rev_months}
        exp_m = {e['month']: e['total'] for e in exp_months}
        for m in all_months:
            r = rev_m.get(m, Decimal('0'))
            e = exp_m.get(m, Decimal('0'))
            cash_flow.append({
                'month': m.strftime('%m/%Y'),
                'inflow': r,
                'outflow': e,
                'net': r - e,
            })
        context['cash_flow_data'] = cash_flow

        # Revenue by Project
        rev_by_proj = (
            Invoice.objects.filter(inv_filter)
            .values('project__name')
            .annotate(total=Sum('total_amount'))
            .order_by('-total')
        )
        context['revenue_by_project'] = rev_by_proj

        # Expense by Department
        dept_expenses = defaultdict(Decimal)
        for exp in Expense.objects.filter(exp_filter).select_related('project'):
            for dept in exp.project.departments.all():
                dept_expenses[dept.name] += exp.amount
        context['expense_by_department'] = sorted(
            [{'name': n, 'total': t} for n, t in dept_expenses.items()],
            key=lambda x: x['total'],
            reverse=True,
        )

        # Budget vs Actual
        bva = (
            Budget.objects.filter(approval_status='approved')
            .values('project__name')
            .annotate(
                total_budget=Sum('allocated_amount'),
                total_spent=Sum('spent_amount'),
            )
            .order_by('project__name')
        )
        for item in bva:
            item['variance'] = item['total_budget'] - item['total_spent']
        context['budget_vs_actual'] = bva

        return context


class CFOReportExportView(PermissionRequiredMixin, View):
    """Export CFO reports as CSV."""
    permission_required = 'view_financial_report'

    def get(self, request):
        report_type = request.GET.get('type', 'profit_loss')
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        filename = f'cfo_{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)

        # Parse filters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        project_id = request.GET.get('project')

        inv_filter = Q(status='paid')
        exp_filter = Q(approval_status='approved')
        if date_from:
            inv_filter &= Q(issue_date__gte=date_from)
            exp_filter &= Q(expense_date__gte=date_from)
        if date_to:
            inv_filter &= Q(issue_date__lte=date_to)
            exp_filter &= Q(expense_date__lte=date_to)
        if project_id:
            inv_filter &= Q(project_id=project_id)
            exp_filter &= Q(project_id=project_id)

        if report_type == 'profit_loss':
            writer.writerow(['Dự án', 'Doanh thu', 'Chi phí', 'Lợi nhuận'])
            projects_qs = Project.objects.all().order_by('name')
            if project_id:
                projects_qs = projects_qs.filter(id=project_id)
            for p in projects_qs:
                rev = Invoice.objects.filter(inv_filter, project=p).aggregate(
                    t=Coalesce(Sum('total_amount'), Decimal('0'))
                )['t']
                cost = Expense.objects.filter(exp_filter, project=p).aggregate(
                    t=Coalesce(Sum('amount'), Decimal('0'))
                )['t']
                writer.writerow([p.name, float(rev), float(cost), float(rev - cost)])

        elif report_type == 'cash_flow':
            writer.writerow(['Tháng', 'Doanh thu', 'Chi phí', 'Dòng tiền ròng'])
            rev_months = (
                Invoice.objects.filter(inv_filter)
                .annotate(month=TruncMonth('issue_date'))
                .values('month').annotate(total=Sum('total_amount')).order_by('month')
            )
            exp_months = (
                Expense.objects.filter(exp_filter)
                .annotate(month=TruncMonth('expense_date'))
                .values('month').annotate(total=Sum('amount')).order_by('month')
            )
            all_m = sorted(set([r['month'] for r in rev_months] + [e['month'] for e in exp_months]))
            rev_m = {r['month']: r['total'] for r in rev_months}
            exp_m = {e['month']: e['total'] for e in exp_months}
            for m in all_m:
                r = rev_m.get(m, Decimal('0'))
                e = exp_m.get(m, Decimal('0'))
                writer.writerow([m.strftime('%m/%Y'), float(r), float(e), float(r - e)])

        elif report_type == 'budget_vs_actual':
            writer.writerow(['Dự án', 'Ngân sách', 'Chi tiêu', 'Chênh lệch'])
            bva = (
                Budget.objects.filter(approval_status='approved')
                .values('project__name')
                .annotate(tb=Sum('allocated_amount'), ts=Sum('spent_amount'))
                .order_by('project__name')
            )
            for b in bva:
                writer.writerow([b['project__name'], float(b['tb']), float(b['ts']), float(b['tb'] - b['ts'])])

        elif report_type == 'revenue_by_project':
            writer.writerow(['Dự án', 'Doanh thu'])
            data = (
                Invoice.objects.filter(inv_filter)
                .values('project__name')
                .annotate(total=Sum('total_amount'))
                .order_by('-total')
            )
            for d in data:
                writer.writerow([d['project__name'], float(d['total'])])

        elif report_type == 'expense_by_department':
            writer.writerow(['Phòng ban', 'Chi phí'])
            dept_expenses = defaultdict(Decimal)
            for exp in Expense.objects.filter(exp_filter).select_related('project'):
                for dept in exp.project.departments.all():
                    dept_expenses[dept.name] += exp.amount
            for name, total in sorted(dept_expenses.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([name, float(total)])

        return response
