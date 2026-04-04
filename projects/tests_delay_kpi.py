from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clients.models import Client
from projects.delay_kpi_service import DelayKPIService
from projects.models import DelayRuleConfig, Project, Task
from resources.models import Department, Employee


class DelayKPIServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pm", password="123456")
        self.emp_user = User.objects.create_user(username="emp1", password="123456")
        self.dept = Department.objects.create(name="IT", code="IT")
        self.employee = Employee.objects.create(
            user=self.emp_user,
            employee_id="E001",
            first_name="Anh",
            last_name="Nguyen",
            email="anh@example.com",
            department=self.dept,
            is_active=True,
            kpi_current=Decimal("100"),
        )
        self.client = Client.objects.create(name="Client A")
        self.project = Project.objects.create(
            name="P1",
            client=self.client,
            status="active",
            priority="medium",
            created_by=self.user,
            delay_penalty_enabled=True,
        )
        DelayRuleConfig.objects.create(is_active=True)

    def test_overdue_task_updates_days_late_and_score(self):
        due = timezone.now().date() - timedelta(days=4)
        task = Task.objects.create(
            project=self.project,
            name="Task Late",
            assigned_to=self.employee,
            status="done",
            due_date=due,
            completed_at=timezone.now(),
            priority="medium",
            delay_reason_type="self",
        )
        DelayKPIService.update_task_delay_metrics(task, actor=self.user)
        task.refresh_from_db()
        self.employee.refresh_from_db()

        self.assertGreater(task.days_late, 0)
        self.assertGreater(task.delay_score, 0)
        self.assertLess(self.employee.kpi_current, Decimal("100"))
        self.assertGreaterEqual(self.employee.penalty_level, 1)

    def test_approved_external_delay_exempts_penalty(self):
        due = timezone.now().date() - timedelta(days=6)
        task = Task.objects.create(
            project=self.project,
            name="Task External",
            assigned_to=self.employee,
            status="done",
            due_date=due,
            completed_at=timezone.now(),
            priority="critical",
            delay_reason_type="external",
            approved_delay=True,
        )
        DelayKPIService.update_task_delay_metrics(task, actor=self.user)
        task.refresh_from_db()

        self.assertEqual(task.days_late, 6)
        self.assertEqual(task.delay_score, Decimal("0"))

    def test_early_completion_reward(self):
        due = timezone.now().date() + timedelta(days=3)
        task = Task.objects.create(
            project=self.project,
            name="Task Early",
            assigned_to=self.employee,
            status="done",
            due_date=due,
            completed_at=timezone.now(),
            priority="medium",
            delay_reason_type="self",
        )
        DelayKPIService.update_task_delay_metrics(task, actor=self.user)
        self.employee.refresh_from_db()
        self.assertGreaterEqual(self.employee.kpi_current, Decimal("100"))
