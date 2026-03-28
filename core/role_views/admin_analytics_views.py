"""
Admin Analytics View - Phân tích chuyên sâu hệ thống ERP.
"""
from django.views.generic import TemplateView
from core.rbac import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class AdminAnalyticsView(PermissionRequiredMixin, TemplateView):
    """Admin Analytics page với các biểu đồ phân tích chuyên sâu."""
    template_name = 'modules/admin/pages/analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Import models
        from resources.models import Department, Employee
        from projects.models import Project, Task
        from core.models import AuditLog

        now = timezone.now()
        
        # Get filter parameters
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        department_id = self.request.GET.get('department', '')
        project_status = self.request.GET.get('project_status', '')
        
        # Base date range (last 6 months)
        if date_from and date_to:
            try:
                from datetime import datetime
                start_date = datetime.strptime(date_from, '%Y-%m-%d')
                end_date = datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                end_date = now
                start_date = now - timedelta(days=180)
        else:
            end_date = now
            start_date = now - timedelta(days=180)

        # ==================== CHART 1: User Growth Analytics ====================
        user_growth_data = []
        for i in range(5, -1, -1):
            month_date = end_date - timedelta(days=30*i)
            month_start = month_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            count = User.objects.filter(
                date_joined__gte=month_start,
                date_joined__lte=month_end
            ).count()
            
            user_growth_data.append({
                'month': month_start.strftime('%m/%Y'),
                'count': count
            })
        
        ctx['user_growth_labels'] = [d['month'] for d in user_growth_data]
        ctx['user_growth_data'] = [d['count'] for d in user_growth_data]

        # ==================== CHART 2: Employee Distribution by Department ====================
        dept_data = Department.objects.annotate(
            emp_count=Count('employee', filter=Q(employee__is_active=True))
        ).order_by('-emp_count')

        ctx['dept_labels'] = [d.name for d in dept_data]
        ctx['dept_data'] = [d.emp_count for d in dept_data]

        # ==================== CHART 3: Project Status Analytics ====================
        project_status_counts = Project.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        status_map = {
            'planning': 'Planning',
            'active': 'Active',
            'on_hold': 'On Hold',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
        }
        
        ctx['project_status_labels'] = [
            status_map.get(item['status'], item['status']) 
            for item in project_status_counts
        ]
        ctx['project_status_data'] = [item['count'] for item in project_status_counts]

        # ==================== CHART 4: Task Completion Analytics ====================
        task_status_counts = Task.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        task_status_map = {
            'todo': 'To Do',
            'in_progress': 'In Progress',
            'review': 'Review',
            'done': 'Done',
        }
        
        ctx['task_status_labels'] = [
            task_status_map.get(item['status'], item['status']) 
            for item in task_status_counts
        ]
        ctx['task_status_data'] = [item['count'] for item in task_status_counts]

        # ==================== CHART 5: Project Creation Trend ====================
        project_trend_data = []
        for i in range(5, -1, -1):
            month_date = end_date - timedelta(days=30*i)
            month_start = month_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            count = Project.objects.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            
            project_trend_data.append({
                'month': month_start.strftime('%m/%Y'),
                'count': count
            })
        
        ctx['project_trend_labels'] = [d['month'] for d in project_trend_data]
        ctx['project_trend_data'] = [d['count'] for d in project_trend_data]

        # ==================== CHART 6: Workload Distribution ====================
        # Get employees with their task counts
        workload_data = Employee.objects.filter(
            is_active=True
        ).annotate(
            task_count=Count('assigned_tasks')
        ).order_by('-task_count')[:15]  # Top 15 employees
        
        ctx['workload_labels'] = [emp.full_name for emp in workload_data]
        ctx['workload_data'] = [emp.task_count for emp in workload_data]

        # ==================== TABLE 1: Top Active Projects ====================
        top_projects = Project.objects.annotate(
            tasks_count=Count('tasks'),
            task_completion=Count('tasks', filter=Q(tasks__status='done'))
        ).order_by('-tasks_count')[:10]
        
        for proj in top_projects:
            proj.completion_percent = round(
                (proj.task_completion / proj.tasks_count * 100) if proj.tasks_count > 0 else 0, 1
            )
        
        ctx['top_projects'] = top_projects

        # ==================== TABLE 2: Most Active Employees ====================
        active_employees = Employee.objects.filter(
            is_active=True
        ).annotate(
            tasks_assigned=Count('assigned_tasks'),
            tasks_completed=Count('assigned_tasks', filter=Q(assigned_tasks__status='done'))
        ).order_by('-tasks_assigned')[:10]

        ctx['active_employees'] = active_employees

        # ==================== TABLE 3: System Activity Summary ====================
        from django.core.paginator import Paginator
        
        all_activities = AuditLog.objects.select_related('user').order_by('-created_at')
        activities_paginator = Paginator(all_activities, 10)  # 10 per page
        page_number = self.request.GET.get('activity_page', 1)
        activities_page = activities_paginator.get_page(page_number)
        
        ctx['recent_activities'] = activities_page
        ctx['activities_paginator'] = activities_paginator
        ctx['activities_page'] = activities_page

        # ==================== Filter Options ====================
        ctx['departments'] = Department.objects.filter(is_active=True).order_by('name')
        ctx['project_statuses'] = Project.STATUS_CHOICES
        ctx['current_department'] = department_id
        ctx['current_project_status'] = project_status
        ctx['current_date_from'] = date_from
        ctx['current_date_to'] = date_to

        return ctx
