from .models import Task, TaskHistory


class TaskHistoryService:
    @staticmethod
    def employee_skills_text(employee):
        if not employee:
            return ''
        parts = []
        if getattr(employee, 'position_fk', None):
            parts.append(employee.position_fk.name)
        if getattr(employee, 'position', None):
            parts.append(employee.position)
        if getattr(employee, 'department', None):
            parts.append(employee.department.name)
        seen = []
        for p in parts:
            p = (p or '').strip()
            if p and p not in seen:
                seen.append(p)
        return ', '.join(seen)

    @staticmethod
    def current_workload(employee, exclude_task_id=None):
        if not employee:
            return 0
        qs = Task.objects.filter(
            assigned_to=employee,
            assignment_status__in=['accepted', 'in_progress'],
        ).exclude(status__in=['done', 'cancelled'])
        if exclude_task_id:
            qs = qs.exclude(pk=exclude_task_id)
        return qs.count()

    @classmethod
    def update_task_snapshots(cls, task):
        employee = task.assigned_to
        if not employee:
            task.assignee_skills_snapshot = ''
            task.workload_snapshot = 0
            return
        task.assignee_skills_snapshot = cls.employee_skills_text(employee)
        task.workload_snapshot = cls.current_workload(employee, exclude_task_id=task.pk)

    @classmethod
    def log(cls, task, actor=None, event_type='updated', note=''):
        employee = task.assigned_to
        workload = cls.current_workload(employee, exclude_task_id=task.pk) if employee else 0
        TaskHistory.objects.create(
            task=task,
            event_type=event_type,
            event_note=note or '',
            task_name_snapshot=task.name or '',
            task_description_snapshot=task.description or '',
            assigned_to=employee,
            required_skills_snapshot=task.required_skills or '',
            employee_skills_snapshot=cls.employee_skills_text(employee),
            started_at_snapshot=task.started_at,
            due_date_snapshot=task.due_date,
            completed_at_snapshot=task.completed_at,
            status_snapshot=task.status or '',
            assignment_status_snapshot=task.assignment_status or '',
            delay_note_snapshot=task.delay_explanation or '',
            workload_at_time=workload,
            created_by=actor,
            updated_by=actor,
        )
