from django.contrib import admin
from .models import Project, Task, TimeEntry


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'status', 'priority', 'start_date', 'end_date', 'estimated_budget']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['name', 'description']
    date_hierarchy = 'created_at'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'status', 'assigned_to', 'due_date', 'estimated_hours', 'actual_hours']
    list_filter = ['status', 'project', 'created_at']
    search_fields = ['name', 'description']
    date_hierarchy = 'due_date'


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'task', 'date', 'hours']
    list_filter = ['date', 'employee', 'task__project']
    search_fields = ['employee__first_name', 'employee__last_name', 'task__name']
    date_hierarchy = 'date'

