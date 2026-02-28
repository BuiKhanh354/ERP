"""Core business logic services."""
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from projects.models import Project, Task, TimeEntry
from resources.models import Employee, ResourceAllocation
from budgeting.models import Budget, Expense
from clients.models import Client
from performance.models import PerformanceScore


class DashboardService:
    """Service để tính toán các metrics cho dashboard."""

    @staticmethod
    def get_project_overview(user):
        """Tổng quan dự án đang chạy - filter theo user và role."""
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if is_manager:
            # Quản lý xem tất cả projects
            user_projects = Project.objects.all()
        else:
            # Nhân viên chỉ xem projects được phân bổ vào (ResourceAllocation)
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                user_projects = Project.objects.filter(id__in=allocated_project_ids)
            else:
                user_projects = Project.objects.none()
        
        # Tối ưu: Sử dụng annotate để đếm tasks trong một query
        from django.db.models import Count, Case, When, IntegerField
        
        # Đếm số projects theo status trong một query
        # SQL Server yêu cầu order_by phải match với GROUP BY, nên cần override ordering
        status_counts = user_projects.values('status').annotate(count=Count('id')).order_by('status')
        status_dict = {item['status']: item['count'] for item in status_counts}
        
        total_projects = sum(status_dict.values())
        active_projects = status_dict.get('active', 0)
        planning_projects = status_dict.get('planning', 0)
        completed_projects = status_dict.get('completed', 0)
        on_hold_projects = status_dict.get('on_hold', 0)

        # Tối ưu: Sử dụng annotate để tính completion rate trong một query
        projects_with_completion = []
        # SQL Server yêu cầu order_by phải match với GROUP BY khi dùng annotate
        projects_qs = user_projects.filter(status__in=['active', 'completed']).annotate(
            total_tasks=Count('tasks'),
            completed_tasks=Count('tasks', filter=Q(tasks__status='done'))
        ).only('id', 'name', 'status').order_by('id')
        
        for project in projects_qs:
            total = project.total_tasks
            completed = project.completed_tasks
            completion_rate = (completed / total * 100) if total > 0 else 0
            projects_with_completion.append({
                'id': project.id,
                'name': project.name,
                'status': project.get_status_display(),
                'completion_rate': round(completion_rate, 1),
                'total_tasks': total,
                'completed_tasks': completed,
            })

        return {
            'total': total_projects,
            'active': active_projects,
            'planning': planning_projects,
            'completed': completed_projects,
            'on_hold': on_hold_projects,
            'projects_completion': projects_with_completion,
        }

    @staticmethod
    def get_resource_workload(user, period='week'):
        """Workload nhân sự theo tuần/tháng - filter theo user và role."""
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if period == 'week':
            start_date = timezone.now().date() - timedelta(days=7)
        else:  # month
            start_date = timezone.now().date() - timedelta(days=30)

        # Tính workload từ TimeEntry
        if is_manager:
            # Quản lý xem tất cả TimeEntry
            workload_data = TimeEntry.objects.filter(
                date__gte=start_date
            ).values('employee').annotate(
                total_hours=Sum('hours')
            ).order_by('-total_hours')
        else:
            # Nhân viên chỉ xem TimeEntry của chính mình
            employee = getattr(user, 'employee', None)
            if employee:
                workload_data = TimeEntry.objects.filter(
                    date__gte=start_date,
                    employee=employee
                ).values('employee').annotate(
                    total_hours=Sum('hours')
                ).order_by('-total_hours')
            else:
                workload_data = TimeEntry.objects.none()

        workload_list = []
        for item in workload_data:
            try:
                if is_manager:
                    # Quản lý xem tất cả employees
                    employee = Employee.objects.get(id=item['employee'])
                else:
                    # Nhân viên chỉ xem employees do mình tạo
                    employee = Employee.objects.get(id=item['employee'], created_by=user)
                workload_list.append({
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'total_hours': float(item['total_hours']),
                    'department': employee.department.name if employee.department else 'N/A',
                })
            except Employee.DoesNotExist:
                continue

        return workload_list

    @staticmethod
    def get_budget_summary(user):
        """Tổng chi phí / dự toán - filter theo user và role."""
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if is_manager:
            # Quản lý xem tất cả budgets
            total_budget = Budget.objects.all().aggregate(
                total_allocated=Sum('allocated_amount'),
                total_spent=Sum('spent_amount')
            )
        else:
            # Nhân viên chỉ lấy budgets của projects được phân bổ
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                total_budget = Budget.objects.filter(
                    project_id__in=allocated_project_ids
                ).aggregate(
                    total_allocated=Sum('allocated_amount'),
                    total_spent=Sum('spent_amount')
                )
            else:
                total_budget = {'total_allocated': None, 'total_spent': None}

        allocated = total_budget['total_allocated'] or Decimal('0')
        spent = total_budget['total_spent'] or Decimal('0')
        remaining = allocated - spent
        utilization_rate = (spent / allocated * 100) if allocated > 0 else 0

        return {
            'total_allocated': float(allocated),
            'total_spent': float(spent),
            'remaining': float(remaining),
            'utilization_rate': round(utilization_rate, 2),
        }

    @staticmethod
    def get_alerts(user):
        """Cảnh báo deadline, quá tải, overbudget - filter theo user và role."""
        alerts = []
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        today = timezone.now().date()

        # Deadline sắp đến (trong 7 ngày) - Tối ưu: chỉ lấy fields cần thiết
        if is_manager:
            # Quản lý xem tất cả tasks
            upcoming_deadlines = Task.objects.filter(
                due_date__lte=today + timedelta(days=7),
                due_date__gte=today,
                status__in=['todo', 'in_progress']
            ).select_related('project').only('id', 'name', 'due_date', 'project__id', 'project__name')
        else:
            # Nhân viên chỉ xem tasks được assign cho mình
            employee = getattr(user, 'employee', None)
            if employee:
                upcoming_deadlines = Task.objects.filter(
                    assigned_to=employee,
                    due_date__lte=today + timedelta(days=7),
                    due_date__gte=today,
                    status__in=['todo', 'in_progress']
                ).select_related('project').only('id', 'name', 'due_date', 'project__id', 'project__name')
            else:
                upcoming_deadlines = Task.objects.none()

        for task in upcoming_deadlines:
            days_left = (task.due_date - today).days
            alerts.append({
                'type': 'deadline',
                'severity': 'warning' if days_left <= 3 else 'info',
                'message': f'Task "{task.name}" của dự án "{task.project.name}" sắp đến hạn ({days_left} ngày)',
                'task_id': task.id,
                'project_id': task.project.id,
            })

        # Quá hạn (due_date < today) và chưa hoàn thành
        if is_manager:
            overdue_tasks = Task.objects.filter(
                due_date__lt=today,
                status__in=['todo', 'in_progress', 'review']
            ).select_related('project').only('id', 'name', 'due_date', 'project__id', 'project__name')[:50]
        else:
            # Nhân viên chỉ xem tasks được assign cho mình
            employee = getattr(user, 'employee', None)
            if employee:
                overdue_tasks = Task.objects.filter(
                    assigned_to=employee,
                    due_date__lt=today,
                    status__in=['todo', 'in_progress', 'review']
                ).select_related('project').only('id', 'name', 'due_date', 'project__id', 'project__name')[:50]
            else:
                overdue_tasks = Task.objects.none()

        for task in overdue_tasks:
            days_over = (today - task.due_date).days
            alerts.append({
                'type': 'overdue',
                'severity': 'danger',
                'message': f'Task "{task.name}" của dự án "{task.project.name}" đã quá hạn ({days_over} ngày) và chưa hoàn thành',
                'task_id': task.id,
                'project_id': task.project.id,
            })

        # Quá tải nhân sự (workload > 40h/tuần)
        # Chỉ hiển thị cho quản lý, nhân viên không cần cảnh báo này
        if is_manager:
            workload_data = DashboardService.get_resource_workload(user, 'week')
            for item in workload_data:
                if item['total_hours'] > 40:
                    alerts.append({
                        'type': 'overload',
                        'severity': 'danger',
                        'message': f'{item["employee_name"]} đang quá tải ({item["total_hours"]:.1f}h/tuần)',
                        'employee_id': item['employee_id'],
                    })

        # Overbudget (chi tiêu > 90% ngân sách) - Tối ưu: chỉ lấy projects có utilization >= 90
        # SQL Server yêu cầu order_by phải match với GROUP BY khi dùng annotate
        if is_manager:
            # Quản lý xem tất cả projects
            overbudget_projects = Project.objects.annotate(
                total_spent=Sum('budgets__spent_amount'),
                total_allocated=Sum('budgets__allocated_amount')
            ).filter(
                total_allocated__gt=0
            ).only('id', 'name').order_by('id')
        else:
            # Nhân viên chỉ xem projects được phân bổ
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                overbudget_projects = Project.objects.filter(
                    id__in=allocated_project_ids
                ).annotate(
                    total_spent=Sum('budgets__spent_amount'),
                    total_allocated=Sum('budgets__allocated_amount')
                ).filter(
                    total_allocated__gt=0
                ).only('id', 'name').order_by('id')
            else:
                overbudget_projects = Project.objects.none()

        for project in overbudget_projects:
            if project.total_allocated > 0:
                utilization = (project.total_spent / project.total_allocated * 100) if project.total_spent else 0
                if utilization >= 90:
                    alerts.append({
                        'type': 'overbudget',
                        'severity': 'danger' if utilization >= 100 else 'warning',
                        'message': f'Dự án "{project.name}" đã sử dụng {utilization:.1f}% ngân sách',
                        'project_id': project.id,
                        'utilization': round(utilization, 1),
                    })

        return alerts

    @staticmethod
    def get_dashboard_stats(user):
        """Tổng hợp tất cả stats cho dashboard - filter theo user và role."""
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if is_manager:
            # Quản lý xem tất cả
            total_employees = Employee.objects.filter(is_active=True).count()
            active_clients = Client.objects.filter(status='active').count()
        else:
            # Nhân viên chỉ xem của mình
            total_employees = Employee.objects.filter(is_active=True, created_by=user).count()
            active_clients = Client.objects.filter(status='active', created_by=user).count()
        
        return {
            'projects': DashboardService.get_project_overview(user),
            'workload': DashboardService.get_resource_workload(user, 'week'),
            'budget': DashboardService.get_budget_summary(user),
            'alerts': DashboardService.get_alerts(user),
            'total_employees': total_employees,
            'active_clients': active_clients,
            'monthly_expense_data': DashboardService.get_monthly_expense_data(user),
        }

    @staticmethod
    def get_monthly_expense_data(user):
        """Lấy dữ liệu chi tiêu theo tháng (4 tuần gần nhất) - filter theo user và role."""
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        from datetime import date
        today = timezone.now().date()
        
        # Tính 4 tuần gần nhất
        weekly_labels = []
        weekly_actual = []
        weekly_budget = []
        
        # Tối ưu: Lấy tất cả expenses trong khoảng thời gian một lần
        week_start_first = today - timedelta(days=3*7 + today.weekday())
        week_end_last = today + timedelta(days=6)
        
        if is_manager:
            all_expenses = Expense.objects.filter(
                expense_date__gte=week_start_first,
                expense_date__lte=week_end_last
            ).values('expense_date', 'amount')
        else:
            # Nhân viên chỉ xem expenses của projects được phân bổ
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                all_expenses = Expense.objects.filter(
                    expense_date__gte=week_start_first,
                    expense_date__lte=week_end_last,
                    project_id__in=allocated_project_ids
                ).values('expense_date', 'amount')
            else:
                all_expenses = Expense.objects.none()
        
        # Nhóm expenses theo tuần
        weekly_expenses_dict = {}
        for expense in all_expenses:
            expense_date = expense['expense_date']
            days_diff = (expense_date - week_start_first).days
            week_index = days_diff // 7
            if week_index < 4:
                if week_index not in weekly_expenses_dict:
                    weekly_expenses_dict[week_index] = Decimal('0')
                weekly_expenses_dict[week_index] += expense['amount']
        
        # Lấy chi tiêu thực tế cho 4 tuần
        weekly_actual_list = []
        for i in range(4):
            actual_spent = float(weekly_expenses_dict.get(i, Decimal('0')))
            weekly_actual_list.append(actual_spent)
            weekly_labels.append(f'Tuần {i+1}')
            weekly_actual.append(actual_spent)
        
        # Sử dụng AI để dự đoán budget cho từng tuần (chỉ khi có dữ liệu)
        from ai.services import AIService
        try:
            if any(weekly_actual_list):
                predicted_budgets = AIService.predict_weekly_budget(user, weekly_actual_list)
                weekly_budget = predicted_budgets
            else:
                weekly_budget = [0.0] * 4
        except Exception as e:
            # Fallback: Nếu AI lỗi, dùng trung bình chi tiêu * 1.2
            avg_expense = sum(weekly_actual_list) / len(weekly_actual_list) if weekly_actual_list and any(weekly_actual_list) else 0
            weekly_budget = [float(avg_expense * 1.2)] * 4
        
        return {
            'labels': weekly_labels,
            'actual': weekly_actual,
            'budget': weekly_budget,
        }