from django.views.generic import TemplateView, CreateView, ListView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum
from core.rbac import PermissionRequiredMixin
from resources.models import Employee
from projects.models import TimeEntry, Task


class EmployeeDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'modules/employee/pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            employee = Employee.objects.select_related('department', 'user').get(user=self.request.user)
        except Employee.DoesNotExist:
            context.update(
                {
                    'employee': None,
                    'assigned_tasks_count': 0,
                    'completed_tasks_count': 0,
                    'overdue_tasks_count': 0,
                    'completion_rate': 0,
                    'hours_this_month': 0,
                    'upcoming_tasks': [],
                }
            )
            return context

        assigned_tasks = Task.objects.filter(assigned_to=employee)
        assigned_tasks_count = assigned_tasks.count()
        completed_tasks_count = assigned_tasks.filter(status='done').count()
        overdue_tasks_count = assigned_tasks.filter(
            due_date__lt=timezone.localdate()
        ).exclude(status='done').count()
        completion_rate = round((completed_tasks_count / assigned_tasks_count * 100), 2) if assigned_tasks_count else 0

        month_start = timezone.localdate().replace(day=1)
        hours_this_month = (
            TimeEntry.objects.filter(employee=employee, date__gte=month_start)
            .aggregate(total=Sum('hours'))['total']
            or 0
        )

        upcoming_tasks = assigned_tasks.exclude(status='done').order_by('due_date', 'created_at')[:5]

        context.update(
            {
                'employee': employee,
                'assigned_tasks_count': assigned_tasks_count,
                'completed_tasks_count': completed_tasks_count,
                'overdue_tasks_count': overdue_tasks_count,
                'completion_rate': completion_rate,
                'hours_this_month': hours_this_month,
                'upcoming_tasks': upcoming_tasks,
            }
        )
        return context


class EmployeeTimeEntryView(LoginRequiredMixin, CreateView):
    """View for employees to create time entries."""
    template_name = 'modules/employee/pages/time_entry.html'
    success_url = reverse_lazy('employee_module:time-entry-list')

    def get_form_class(self):
        from projects.forms import TimeEntryForm
        return TimeEntryForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Filter tasks to only assigned tasks for this employee
        try:
            employee = Employee.objects.get(user=self.request.user)
            kwargs['employee'] = employee
            # Only show tasks assigned to this employee
            kwargs['tasks'] = Task.objects.filter(assigned_to=employee)
        except Employee.DoesNotExist:
            kwargs['employee'] = None
            kwargs['tasks'] = Task.objects.none()
        return kwargs

    def form_valid(self, form):
        # Set employee from current user
        try:
            form.instance.employee = Employee.objects.get(user=self.request.user)
        except Employee.DoesNotExist:
            form.add_error(None, "You don't have an employee record. Please contact HR.")
            return self.form_invalid(form)
        return super().form_valid(form)


class EmployeeTimeEntryListView(LoginRequiredMixin, ListView):
    """View for employees to view their time entry history."""
    template_name = 'modules/employee/pages/time_entry_list.html'
    context_object_name = 'time_entries'

    def get_queryset(self):
        try:
            employee = Employee.objects.get(user=self.request.user)
            return TimeEntry.objects.filter(employee=employee).order_by('-date', '-created_at')
        except Employee.DoesNotExist:
            return TimeEntry.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            employee = Employee.objects.get(user=self.request.user)
            # Calculate total hours this month
            from datetime import timedelta
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            time_entries = TimeEntry.objects.filter(
                employee=employee,
                date__gte=start_date,
                date__lte=end_date
            )
            total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
            context['total_hours_this_month'] = total_hours
        except Employee.DoesNotExist:
            context['total_hours_this_month'] = 0
        return context
