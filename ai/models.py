from django.db import models
from core.models import BaseModel


class AIInsight(BaseModel):
    """Stored AI-generated insights."""
    INSIGHT_TYPE_CHOICES = [
        ('resource_performance', 'Resource Performance'),
        ('project_staffing', 'Project Staffing'),
        ('sales_improvement', 'Sales Improvement'),
        ('purchasing_improvement', 'Purchasing Improvement'),
        ('budget_optimization', 'Budget Optimization'),
        ('general', 'General'),
    ]

    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    summary = models.TextField()
    insights = models.TextField()  # JSON string of insights array
    recommendations = models.TextField()  # JSON string of recommendations array
    context_data = models.TextField(blank=True)  # JSON string of input context
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.insight_type} - {self.title}"

