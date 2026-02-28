"""Budgeting business logic services."""
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Budget, Expense


class BudgetService:
    """Service class for budget-related operations."""

    @staticmethod
    def get_project_budget_summary(project_id):
        """Get comprehensive budget summary for a project."""
        budgets = Budget.objects.filter(project_id=project_id)
        
        total_allocated = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        total_spent = budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        total_remaining = total_allocated - total_spent
        
        expenses = Expense.objects.filter(project_id=project_id)
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'total_allocated': total_allocated,
            'total_spent': total_spent,
            'total_remaining': total_remaining,
            'total_expenses': total_expenses,
            'utilization_percentage': (total_spent / total_allocated * 100) if total_allocated > 0 else 0,
            'budgets': budgets,
            'expenses': expenses,
        }

    @staticmethod
    def update_budget_spent(budget_id):
        """Update spent amount for a budget based on expenses."""
        budget = Budget.objects.get(id=budget_id)
        expenses = Expense.objects.filter(budget=budget)
        total_spent = expenses.aggregate(total=Sum('amount'))['total'] or 0
        budget.spent_amount = total_spent
        budget.save()
        return budget

