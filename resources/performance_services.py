"""
Service tính điểm hiệu suất nhân sự theo yêu cầu nghiệp vụ:
- Dựa trên mức chi tiêu cho dự án (budget utilization)
- Dựa trên mức độ hoàn thành công việc
"""

from decimal import Decimal

from django.db.models import Sum, Count, Q

from budgeting.models import Budget, Expense
from projects.models import Task
from resources.models import ResourceAllocation, Employee


class EmployeePerformanceService:
    """
    Điểm hiệu suất (0-100) = 60% * % hoàn thành công việc + 40% * điểm tối ưu chi tiêu.

    - % hoàn thành: dựa trên Task assigned_to employee (trong các dự án employee tham gia).
    - Chi tiêu: dựa trên budgets/expenses của các dự án employee tham gia.
      Nếu không có budget -> điểm chi tiêu mặc định 50.
    """

    @staticmethod
    def calculate(employee: Employee) -> dict:
        # Projects mà employee được phân bổ
        project_ids = list(
            ResourceAllocation.objects.filter(employee=employee).values_list("project_id", flat=True).distinct()
        )

        # 1) Completion score
        tasks_qs = Task.objects.filter(assigned_to=employee)
        if project_ids:
            tasks_qs = tasks_qs.filter(project_id__in=project_ids)

        total_tasks = tasks_qs.count()
        done_tasks = tasks_qs.filter(status="done").count()
        completion_rate = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        # 2) Spending score
        if not project_ids:
            spending_score = 50.0
            total_allocated = Decimal("0")
            total_spent = Decimal("0")
        else:
            total_allocated = (
                Budget.objects.filter(project_id__in=project_ids).aggregate(total=Sum("allocated_amount"))["total"]
                or Decimal("0")
            )
            # Ưu tiên lấy theo Expense nếu có, fallback spent_amount
            total_spent_expense = (
                Expense.objects.filter(project_id__in=project_ids).aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )
            total_spent_budget = (
                Budget.objects.filter(project_id__in=project_ids).aggregate(total=Sum("spent_amount"))["total"]
                or Decimal("0")
            )
            total_spent = total_spent_expense if total_spent_expense > 0 else total_spent_budget

            if total_allocated > 0:
                utilization = float((total_spent / total_allocated) * 100)
                utilization = max(0.0, min(200.0, utilization))
                # sử dụng càng thấp càng tốt
                spending_score = max(0.0, 100.0 - min(100.0, utilization))
            else:
                spending_score = 50.0

        # 3) Overall
        overall = 0.6 * completion_rate + 0.4 * spending_score
        overall = max(0.0, min(100.0, overall))

        return {
            "overall": round(overall, 1),
            "completion_rate": round(completion_rate, 1),
            "spending_score": round(spending_score, 1),
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "total_allocated": total_allocated,
            "total_spent": total_spent,
        }

