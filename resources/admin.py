from django.contrib import admin
from .models import Department, Employee, ResourceAllocation, Skill, EmployeeSkill


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'manager', 'created_at']
    search_fields = ['name', 'description']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'employee_id', 'first_name', 'last_name', 'email', 'department',
        'kpi_current', 'penalty_level', 'at_risk', 'is_active'
    ]
    list_filter = ['department', 'employment_type', 'is_active', 'hire_date']
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']
    date_hierarchy = 'hire_date'


@admin.register(ResourceAllocation)
class ResourceAllocationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'project', 'allocation_percentage', 'start_date', 'end_date']
    list_filter = ['start_date', 'project']
    search_fields = ['employee__first_name', 'employee__last_name', 'project__name']
    date_hierarchy = 'start_date'


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'category']


@admin.register(EmployeeSkill)
class EmployeeSkillAdmin(admin.ModelAdmin):
    list_display = ['employee', 'skill', 'proficiency', 'years_of_experience']
    list_filter = ['proficiency', 'skill__category']
    search_fields = ['employee__first_name', 'employee__last_name', 'skill__name']

