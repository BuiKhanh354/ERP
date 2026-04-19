from django.contrib import admin
from .models import Project, Task, TimeEntry, DelayRuleConfig, TaskHistory, ProjectMembershipRequest


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'status', 'priority', 'start_date', 'end_date', 'estimated_budget']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['name', 'description']
    date_hierarchy = 'created_at'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'status', 'assigned_to', 'due_date', 'days_late', 'delay_score', 'workload_snapshot']
    list_filter = ['status', 'project', 'created_at']
    search_fields = ['name', 'description']
    date_hierarchy = 'due_date'


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ['task', 'event_type', 'assigned_to', 'status_snapshot', 'assignment_status_snapshot', 'workload_at_time', 'created_at']
    list_filter = ['event_type', 'status_snapshot', 'assignment_status_snapshot', 'created_at']
    search_fields = ['task__name', 'event_note', 'task_name_snapshot']
    date_hierarchy = 'created_at'


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'task', 'date', 'hours']
    list_filter = ['date', 'employee', 'task__project']
    search_fields = ['employee__first_name', 'employee__last_name', 'task__name']
    date_hierarchy = 'date'


@admin.register(DelayRuleConfig)
class DelayRuleConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'requires_explanation_after_days', 'updated_at']
    list_filter = ['is_active']


@admin.register(ProjectMembershipRequest)
class ProjectMembershipRequestAdmin(admin.ModelAdmin):
    list_display = ['project', 'employee', 'requested_by', 'status', 'created_at']
    list_filter = ['status', 'project']
    search_fields = ['project__name', 'employee__first_name', 'employee__last_name']

