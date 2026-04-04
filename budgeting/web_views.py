"""Web views for Budgeting Management."""
import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from datetime import datetime

from .models import Budget, Expense, BudgetCategory
from .forms import BudgetForm, ExpenseForm
from projects.models import Project
from core.mixins import ManagerRequiredMixin
from core.rbac import get_user_role_names


class BudgetListView(LoginRequiredMixin, ListView):
    """Danh sách ngân sách với filter."""
    model = Budget
    template_name = 'budgeting/list.html'
    context_object_name = 'budgets'
    paginate_by = 20

    def _has_budget_admin_scope(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        profile_manager = hasattr(user, 'profile') and user.profile.is_manager()
        role_names = get_user_role_names(user)
        elevated_roles = {
            'ADMIN', 'CFO', 'HR_ADMIN', 'PROJECT_MANAGER',
            'FINANCE_ADMIN', 'EXECUTIVE', 'RESOURCE_MANAGER', 'ACCOUNTANT',
        }
        return profile_manager or bool(role_names & elevated_roles)

    def get_queryset(self):
        # Quản lý xem tất cả, nhân viên chỉ xem budgets của projects được phân bổ
        user = self.request.user
        is_manager = self._has_budget_admin_scope(user)
        
        if is_manager:
            queryset = Budget.objects.all().select_related('project', 'category').annotate(
                total_expenses=Sum('expenses__amount')
            )
        else:
            # Nhân viên chỉ xem budgets của projects được phân bổ
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                queryset = Budget.objects.filter(
                    project_id__in=allocated_project_ids
                ).select_related('project', 'category').annotate(
                    total_expenses=Sum('expenses__amount')
                )
            else:
                queryset = Budget.objects.none()

        # Filter theo project
        project_id = self.request.GET.get('project')
        if project_id:
            if is_manager:
                queryset = queryset.filter(project_id=project_id)
            else:
                # Đảm bảo project_id trong danh sách allocated projects
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    if int(project_id) in allocated_project_ids:
                        queryset = queryset.filter(project_id=project_id)
                    else:
                        queryset = Budget.objects.none()
                else:
                    queryset = Budget.objects.none()

        # Filter theo category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Filter theo fiscal year
        fiscal_year = self.request.GET.get('fiscal_year')
        if fiscal_year:
            queryset = queryset.filter(fiscal_year=fiscal_year)

        return queryset.order_by('-fiscal_year', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Quản lý xem tất cả, nhân viên chỉ projects được phân bổ
        user = self.request.user
        is_manager = self._has_budget_admin_scope(user)
        if is_manager:
            context['projects'] = Project.objects.all()
        else:
            # Nhân viên chỉ xem projects được phân bổ
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                context['projects'] = Project.objects.filter(id__in=allocated_project_ids)
            else:
                context['projects'] = Project.objects.none()
        context['categories'] = BudgetCategory.objects.all()  # Categories có thể shared
        
        # Lấy budgets để tính fiscal_years
        if is_manager:
            user_budgets = Budget.objects.all()
        else:
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                user_budgets = Budget.objects.filter(project_id__in=allocated_project_ids)
            else:
                user_budgets = Budget.objects.none()
        context['fiscal_years'] = user_budgets.values_list('fiscal_year', flat=True).distinct().order_by('-fiscal_year')
        context['project_filter'] = self.request.GET.get('project', '')
        context['category_filter'] = self.request.GET.get('category', '')
        context['fiscal_year_filter'] = self.request.GET.get('fiscal_year', '')
        
        # Thêm thông tin quyền cho mỗi budget
        budgets_with_permissions = []
        for budget in context['budgets']:
            can_edit = is_manager or budget.project.created_by == user
            can_delete = is_manager or budget.project.created_by == user
            budgets_with_permissions.append({
                'budget': budget,
                'can_edit': can_edit,
                'can_delete': can_delete
            })
        context['budgets_with_permissions'] = budgets_with_permissions
        
        # Stats
        queryset = self.get_queryset()
        context['total_allocated'] = queryset.aggregate(total=Sum('allocated_amount'))['total'] or 0
        context['total_spent'] = queryset.aggregate(total=Sum('spent_amount'))['total'] or 0
        context['total_remaining'] = context['total_allocated'] - context['total_spent']
        
        # Chart data: Budget allocation by project
        budget_by_project = {}
        for budget in queryset.select_related('project'):
            project_name = budget.project.name
            budget_by_project[project_name] = budget_by_project.get(project_name, 0) + float(budget.allocated_amount)
        context['budget_by_project_labels'] = list(budget_by_project.keys())
        context['budget_by_project_data'] = [float(v) for v in budget_by_project.values()]
        
        # Chart data: Spending by category
        spending_by_category = {}
        # Lấy tất cả expenses của các project trong queryset (không giới hạn theo user)
        project_ids = [b.project.id for b in queryset]
        if project_ids:
            expenses = Expense.objects.filter(
                project_id__in=project_ids
            )
            for expense in expenses:
                category_name = expense.category.name
                spending_by_category[category_name] = spending_by_category.get(category_name, 0) + float(expense.amount)
        context['spending_by_category_labels'] = list(spending_by_category.keys())
        context['spending_by_category_data'] = [float(v) for v in spending_by_category.values()]
        
        # Chart data: Utilization by project
        utilization_by_project = {}
        for budget in queryset.select_related('project'):
            project_name = budget.project.name
            if budget.allocated_amount > 0:
                utilization = (budget.spent_amount / budget.allocated_amount) * 100
                if project_name in utilization_by_project:
                    # Average if multiple budgets for same project
                    utilization_by_project[project_name] = (utilization_by_project[project_name] + utilization) / 2
                else:
                    utilization_by_project[project_name] = utilization
        context['utilization_by_project_labels'] = list(utilization_by_project.keys())
        context['utilization_by_project_data'] = [float(v) for v in utilization_by_project.values()]
        
        # Chart data: Monthly spending (last 6 months)
        from datetime import timedelta
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=180)
        monthly_spending = {}
        # Lấy tất cả expenses của các project trong queryset (không giới hạn theo user)
        project_ids = [b.project.id for b in queryset]
        if project_ids:
            expenses_monthly = Expense.objects.filter(
                expense_date__gte=start_date,
                project_id__in=project_ids
            )
            for expense in expenses_monthly:
                month_key = expense.expense_date.strftime('%Y-%m')
                monthly_spending[month_key] = monthly_spending.get(month_key, 0) + float(expense.amount)
        # Sort by month
        sorted_monthly = dict(sorted(monthly_spending.items())) if monthly_spending else {}
        context['monthly_spending_labels'] = list(sorted_monthly.keys())
        context['monthly_spending_data'] = [float(v) for v in sorted_monthly.values()]
        
        return context


class BudgetManageView(BudgetListView):
    """Trang quản lí ngân sách (stats/filter/chart), tách khỏi form tạo mới."""
    template_name = 'budgeting/manage.html'


class BudgetDetailView(LoginRequiredMixin, DetailView):
    """Chi tiết ngân sách với expenses."""
    model = Budget
    template_name = 'budgeting/detail.html'
    context_object_name = 'budget'

    def get_queryset(self):
        """Quản lý xem tất cả, nhân viên chỉ xem budgets của projects được phân bổ."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Budget.objects.all()
        else:
            # Nhân viên chỉ xem budgets của projects được phân bổ
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                return Budget.objects.filter(project_id__in=allocated_project_ids)
            else:
                return Budget.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        budget = self.get_object()
        
        # Expenses - quản lý xem tất cả, nhân viên xem expenses của project được phân bổ
        is_manager = hasattr(self.request.user, 'profile') and self.request.user.profile.is_manager()
        if is_manager:
            expenses_qs = budget.expenses.select_related('category', 'created_by').order_by('-expense_date')
        else:
            # Nhân viên xem tất cả expenses của project (không chỉ expenses họ tạo)
            expenses_qs = budget.expenses.select_related('category', 'created_by').order_by('-expense_date')
        
        context['expenses'] = expenses_qs
        context['total_expenses'] = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
        
        # Thống kê chi tiêu theo user
        expense_stats_by_user = expenses_qs.values(
            'created_by__id',
            'created_by__username',
            'created_by__first_name',
            'created_by__last_name',
            'created_by__email'
        ).annotate(
            total_amount=Sum('amount'),
            expense_count=Count('id')
        ).order_by('-total_amount')
        
        # Format dữ liệu cho template
        context['expense_stats_by_user'] = []
        for stat in expense_stats_by_user:
            if stat['created_by__id']:
                full_name = f"{stat['created_by__first_name'] or ''} {stat['created_by__last_name'] or ''}".strip()
                if not full_name:
                    full_name = stat['created_by__username'] or stat['created_by__email'] or 'Unknown'
                context['expense_stats_by_user'].append({
                    'user_id': stat['created_by__id'],
                    'username': stat['created_by__username'],
                    'full_name': full_name,
                    'email': stat['created_by__email'],
                    'total_amount': stat['total_amount'] or 0,
                    'expense_count': stat['expense_count'] or 0,
                })
        
        return context
        
        # Utilization
        context['utilization_percentage'] = budget.utilization_percentage
        context['remaining_amount'] = budget.remaining_amount
        
        return context


class BudgetCreateView(ManagerRequiredMixin, CreateView):
    """Tạo ngân sách mới - chỉ quản lý mới có quyền."""
    model = Budget
    form_class = BudgetForm
    template_name = 'budgeting/form.html'
    success_url = reverse_lazy('budgeting:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Đã tạo ngân sách "{form.instance.category.name}" cho dự án "{form.instance.project.name}" thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Tạo ngân sách mới'
        context['submit_text'] = 'Tạo ngân sách'
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            context['projects'] = Project.objects.all()
        else:
            context['projects'] = Project.objects.filter(created_by=user)
        context['categories'] = BudgetCategory.objects.all()
        return context


class BudgetUpdateView(ManagerRequiredMixin, UpdateView):
    """Cập nhật ngân sách - chỉ quản lý."""
    model = Budget
    form_class = BudgetForm
    template_name = 'budgeting/form.html'
    success_url = reverse_lazy('budgeting:list')

    def get_queryset(self):
        """Quản lý có thể sửa tất cả."""
        return Budget.objects.all()

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Đã cập nhật ngân sách thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Chỉnh sửa ngân sách'
        context['submit_text'] = 'Cập nhật'
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            context['projects'] = Project.objects.all()
        else:
            context['projects'] = Project.objects.filter(created_by=user)
        context['categories'] = BudgetCategory.objects.all()
        return context


class BudgetDeleteView(ManagerRequiredMixin, DeleteView):
    """Xóa ngân sách - chỉ quản lý."""
    model = Budget
    template_name = 'budgeting/confirm_delete.html'
    success_url = reverse_lazy('budgeting:list')

    def get_queryset(self):
        """Quản lý có thể xóa tất cả."""
        return Budget.objects.all()

    def delete(self, request, *args, **kwargs):
        budget = self.get_object()
        messages.success(self.request, f'Đã xóa ngân sách "{budget.category.name}" thành công.')
        return super().delete(request, *args, **kwargs)


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    """Tạo chi phí mới - quản lý và nhân viên đều có thể tạo cho projects được phân bổ."""
    model = Expense
    form_class = ExpenseForm
    template_name = 'budgeting/expense_form.html'
    
    def get_success_url(self):
        budget_id = self.request.GET.get('budget')
        if budget_id:
            return reverse_lazy('budgeting:detail', kwargs={'pk': budget_id})
        return reverse_lazy('budgeting:list')

    def form_valid(self, form):
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        # Kiểm tra quyền: nhân viên chỉ có thể tạo expense cho projects được phân bổ
        if not is_manager:
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if not employee:
                messages.error(self.request, 'Bạn không có quyền thêm chi phí.')
                return redirect('budgeting:list')
            
            # Kiểm tra project có được phân bổ cho nhân viên không
            project = form.instance.project
            if not ResourceAllocation.objects.filter(employee=employee, project=project).exists():
                messages.error(self.request, 'Bạn không có quyền thêm chi phí cho dự án này.')
                return redirect('budgeting:list')
        
        form.instance.created_by = self.request.user
        
        # Update budget spent_amount if budget is selected
        if form.instance.budget:
            budget = form.instance.budget
            budget.spent_amount += form.instance.amount
            budget.save()
        
        messages.success(self.request, f'Đã thêm chi phí thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Thêm chi phí'
        context['submit_text'] = 'Thêm chi phí'
        user = self.request.user
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if is_manager:
            context['projects'] = Project.objects.all()
            context['budgets'] = Budget.objects.all()
        else:
            # Nhân viên chỉ xem projects và budgets được phân bổ
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                context['projects'] = Project.objects.filter(id__in=allocated_project_ids)
                context['budgets'] = Budget.objects.filter(project_id__in=allocated_project_ids)
            else:
                context['projects'] = Project.objects.none()
                context['budgets'] = Budget.objects.none()
        
        context['categories'] = BudgetCategory.objects.all()
        
        # Pre-fill budget if provided
        budget_id = self.request.GET.get('budget')
        if budget_id:
            try:
                if is_manager:
                    context['initial_budget'] = Budget.objects.get(pk=budget_id)
                else:
                    # Nhân viên chỉ có thể chọn budget của projects được phân bổ
                    employee = getattr(user, 'employee', None)
                    if employee:
                        from resources.models import ResourceAllocation
                        allocated_project_ids = ResourceAllocation.objects.filter(
                            employee=employee
                        ).values_list('project_id', flat=True).distinct()
                        context['initial_budget'] = Budget.objects.get(
                            pk=budget_id,
                            project_id__in=allocated_project_ids
                        )
                    else:
                        raise Budget.DoesNotExist
                # Set back_url để quay về trang chi tiết ngân sách
                context['back_url'] = reverse_lazy('budgeting:detail', kwargs={'pk': budget_id})
            except Budget.DoesNotExist:
                pass
        
        # Nếu không có back_url, mặc định về trang list
        if 'back_url' not in context:
            context['back_url'] = reverse_lazy('budgeting:list')
        
        return context


class CreateBudgetCategoryView(LoginRequiredMixin, View):
    """API endpoint để tạo danh mục ngân sách mới (AJAX)."""
    def post(self, request):
        from django.http import JsonResponse
        
        if not hasattr(request.user, 'profile') or not request.user.profile.is_manager():
            return JsonResponse({'success': False, 'error': 'Chỉ quản lý mới có quyền tạo danh mục.'})
        
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Tên danh mục không được để trống.'})
        
        # Kiểm tra xem danh mục đã tồn tại chưa
        if BudgetCategory.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'error': f'Danh mục "{name}" đã tồn tại.'})
        
        try:
            category = BudgetCategory.objects.create(
                name=name,
                description=data.get('description', '').strip(),
                parent_id=data.get('parent_id') if data.get('parent_id') else None,
                created_by=request.user
            )
            return JsonResponse({
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Lỗi khi tạo danh mục: {str(e)}'})
