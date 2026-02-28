from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import BaseModel


class PerformanceMetric(BaseModel):
    """Performance metrics for employees and projects."""
    METRIC_TYPE_CHOICES = [
        ('efficiency', 'Efficiency'),
        ('quality', 'Quality'),
        ('productivity', 'Productivity'),
        ('customer_satisfaction', 'Customer Satisfaction'),
        ('cost_effectiveness', 'Cost Effectiveness'),
    ]

    metric_type = models.CharField(max_length=30, choices=METRIC_TYPE_CHOICES)
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, null=True, blank=True, related_name='metrics')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, null=True, blank=True, related_name='metrics')
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    period_start = models.DateField()
    period_end = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-period_end', '-created_at']

    def __str__(self):
        entity = self.employee or self.project
        return f"{entity} - {self.metric_type} ({self.value})"


class PerformanceScore(BaseModel):
    """Overall performance scores."""
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, related_name='scores')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, null=True, blank=True, related_name='scores')
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=0)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=0)
    productivity_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-period_end', '-overall_score']
        unique_together = ['employee', 'project', 'period_start', 'period_end']

    def __str__(self):
        project_str = f" - {self.project.name}" if self.project else ""
        return f"{self.employee.full_name}{project_str} - Score: {self.overall_score}"

