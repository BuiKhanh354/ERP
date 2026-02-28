from django.db import models
from django.core.validators import MinValueValidator
from core.models import BaseModel


class BudgetCategory(BaseModel):
    """Budget category for organizing expenses."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Budget Categories'

    def __str__(self):
        return self.name


class Budget(BaseModel):
    """Budget model for projects."""
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(BudgetCategory, on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    spent_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fiscal_year = models.IntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-fiscal_year', 'category']
        unique_together = ['project', 'category', 'fiscal_year']

    def __str__(self):
        return f"{self.project.name} - {self.category.name} ({self.fiscal_year})"

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    @property
    def utilization_percentage(self):
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0


class Expense(BaseModel):
    """Expense tracking model."""
    EXPENSE_TYPE_CHOICES = [
        ('labor', 'Nhân công'),
        ('material', 'Vật liệu'),
        ('equipment', 'Thiết bị'),
        ('travel', 'Đi lại'),
        ('other', 'Khác'),
    ]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='expenses')
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    category = models.ForeignKey(BudgetCategory, on_delete=models.CASCADE)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField()
    expense_date = models.DateField()
    vendor = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.amount} ({self.expense_date})"

