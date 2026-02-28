from django.contrib import admin
from .models import PerformanceMetric, PerformanceScore


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ['metric_type', 'employee', 'project', 'value', 'period_start', 'period_end']
    list_filter = ['metric_type', 'period_start', 'period_end']
    search_fields = ['employee__first_name', 'employee__last_name', 'project__name']
    date_hierarchy = 'period_end'


@admin.register(PerformanceScore)
class PerformanceScoreAdmin(admin.ModelAdmin):
    list_display = ['employee', 'project', 'overall_score', 'efficiency_score', 'quality_score', 'productivity_score', 'period_end']
    list_filter = ['period_start', 'period_end']
    search_fields = ['employee__first_name', 'employee__last_name', 'project__name']
    date_hierarchy = 'period_end'

