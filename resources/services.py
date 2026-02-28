"""Resources business logic services."""
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Employee, ResourceAllocation
from projects.models import TimeEntry


class EmployeeService:
    """Service class for employee-related operations."""

    @staticmethod
    def get_employee_utilization(employee_id, start_date=None, end_date=None):
        """Calculate employee utilization percentage."""
        employee = Employee.objects.get(id=employee_id)
        
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()

        allocations = ResourceAllocation.objects.filter(
            employee=employee,
            start_date__lte=end_date,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=start_date)
        )

        total_allocation = sum([a.allocation_percentage for a in allocations])
        
        return {
            'employee': employee,
            'total_allocation': total_allocation,
            'available_capacity': max(0, 100 - total_allocation),
            'allocations': allocations,
        }

    @staticmethod
    def get_employee_hours(employee_id, start_date=None, end_date=None):
        """Get total hours worked by employee."""
        employee = Employee.objects.get(id=employee_id)
        
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()

        time_entries = TimeEntry.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )

        total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
        
        return {
            'employee': employee,
            'total_hours': total_hours,
            'time_entries': time_entries,
        }

