from django.views.generic import TemplateView, CreateView, ListView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Sum
from core.rbac import PermissionRequiredMixin
from resources.models import Employee, Skill, EmployeeSkill
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


class EmployeeSkillsView(PermissionRequiredMixin, TemplateView):
    """View for employees to manage their own skills."""

    template_name = 'modules/employee/pages/skills.html'
    permission_required = 'VIEW_ASSIGNED_TASK'

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        try:
            employee = Employee.objects.get(user=request.user)
        except Employee.DoesNotExist:
            messages.error(request, 'Khong tim thay ho so nhan vien.')
            return redirect('employee_module:skills')

        if action == 'add':
            return self._add_skill(request, employee)
        if action == 'edit':
            return self._edit_skill(request, employee)
        if action == 'delete':
            return self._delete_skill(request, employee)

        messages.warning(request, 'Hanh dong khong hop le.')
        return redirect('employee_module:skills')

    def _add_skill(self, request, employee):
        skill_id = request.POST.get('skill_id')
        proficiency = request.POST.get('proficiency', 'beginner')
        years_of_experience = request.POST.get('years_of_experience') or 0
        notes = request.POST.get('notes', '').strip()

        if not skill_id:
            messages.error(request, 'Vui long chon ky nang.')
            return redirect('employee_module:skills')

        try:
            skill = Skill.objects.get(pk=skill_id, is_active=True)
            EmployeeSkill.objects.create(
                employee=employee,
                skill=skill,
                proficiency=proficiency,
                years_of_experience=years_of_experience,
                notes=notes,
                created_by=request.user,
                updated_by=request.user,
            )
            messages.success(request, 'Da them ky nang thanh cong.')
        except Skill.DoesNotExist:
            messages.error(request, 'Ky nang khong ton tai hoac da ngung hoat dong.')
        except IntegrityError:
            messages.warning(request, 'Ky nang nay da ton tai trong danh sach cua ban.')

        return redirect('employee_module:skills')

    def _edit_skill(self, request, employee):
        employee_skill_id = request.POST.get('employee_skill_id')
        proficiency = request.POST.get('proficiency', 'beginner')
        years_of_experience = request.POST.get('years_of_experience') or 0
        notes = request.POST.get('notes', '').strip()

        if not employee_skill_id:
            messages.error(request, 'Khong tim thay ky nang can cap nhat.')
            return redirect('employee_module:skills')

        employee_skill = EmployeeSkill.objects.filter(
            pk=employee_skill_id,
            employee=employee,
        ).select_related('skill').first()

        if not employee_skill:
            messages.error(request, 'Ban khong co quyen sua ky nang nay.')
            return redirect('employee_module:skills')

        employee_skill.proficiency = proficiency
        employee_skill.years_of_experience = years_of_experience
        employee_skill.notes = notes
        employee_skill.updated_by = request.user
        employee_skill.save(update_fields=['proficiency', 'years_of_experience', 'notes', 'updated_by', 'updated_at'])
        messages.success(request, f'Da cap nhat ky nang {employee_skill.skill.name}.')
        return redirect('employee_module:skills')

    def _delete_skill(self, request, employee):
        employee_skill_id = request.POST.get('employee_skill_id')

        if not employee_skill_id:
            messages.error(request, 'Khong tim thay ky nang can xoa.')
            return redirect('employee_module:skills')

        employee_skill = EmployeeSkill.objects.filter(
            pk=employee_skill_id,
            employee=employee,
        ).select_related('skill').first()

        if not employee_skill:
            messages.error(request, 'Ban khong co quyen xoa ky nang nay.')
            return redirect('employee_module:skills')

        skill_name = employee_skill.skill.name
        employee_skill.delete()
        messages.success(request, f'Da xoa ky nang {skill_name}.')
        return redirect('employee_module:skills')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            employee = Employee.objects.get(user=self.request.user)
            employee_skills = EmployeeSkill.objects.filter(employee=employee).select_related('skill')
            all_skills = Skill.objects.filter(is_active=True).order_by('category', 'name')
            context.update(
                {
                    'employee': employee,
                    'employee_skills': employee_skills,
                    'all_skills': all_skills,
                    'proficiency_choices': EmployeeSkill.PROFICIENCY_CHOICES,
                }
            )
        except Employee.DoesNotExist:
            context.update(
                {
                    'employee': None,
                    'employee_skills': [],
                    'all_skills': Skill.objects.filter(is_active=True),
                    'proficiency_choices': EmployeeSkill.PROFICIENCY_CHOICES,
                }
            )
        return context
