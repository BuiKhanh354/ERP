from django.contrib import admin
from .models import BudgetCategory, Budget, Expense


@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    list_filter = ['parent']
    search_fields = ['name', 'description']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['project', 'category', 'allocated_amount', 'spent_amount', 'fiscal_year']
    list_filter = ['fiscal_year', 'category', 'project']
    search_fields = ['project__name', 'category__name']
    readonly_fields = ['spent_amount']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['project', 'category', 'expense_type', 'amount', 'expense_date', 'vendor']
    list_filter = ['expense_type', 'expense_date', 'category']
    search_fields = ['description', 'vendor', 'invoice_number']
    date_hierarchy = 'expense_date'

