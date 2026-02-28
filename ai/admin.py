from django.contrib import admin
from .models import AIInsight


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ['insight_type', 'title', 'is_active', 'created_at']
    list_filter = ['insight_type', 'is_active', 'created_at']
    search_fields = ['title', 'summary']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

