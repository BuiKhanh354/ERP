from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import BaseModel


class Project(BaseModel):
    """Project model for managing service projects."""
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='projects')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_for_personnel = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        help_text='Ngân sách dành cho nhân sự (VNĐ)'
    )
    estimated_employees = models.PositiveIntegerField(default=0, help_text='Số nhân sự dự kiến cho dự án')
    departments = models.ManyToManyField('resources.Department', related_name='projects', blank=True, help_text='Phòng ban phụ trách dự án')
    required_departments = models.ManyToManyField(
        'resources.Department',
        related_name='required_projects',
        blank=True,
        help_text='Các phòng ban bắt buộc cần tham gia dự án'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Task(BaseModel):
    """Task model for project tasks."""
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'Review'),
        ('done', 'Done'),
        ('overdue', 'Overdue'),
    ]

    ASSIGNMENT_STATUS_CHOICES = [
        ('assigned', 'Đã giao'),
        ('accepted', 'Đã nhận'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('rejected', 'Từ chối'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    department = models.ForeignKey('resources.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', help_text='Phòng ban phụ trách công việc')
    assigned_to = models.ForeignKey('resources.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assignment_status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS_CHOICES, default='assigned', help_text='Trạng thái giao/nhận việc')
    due_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    started_at = models.DateTimeField(null=True, blank=True, help_text='Thời điểm bắt đầu tính giờ ước tính')

    class Meta:
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    @property
    def estimated_end_at(self):
        """Tính thời điểm kết thúc ước tính dựa trên started_at hoặc created_at."""
        from django.utils import timezone
        base_time = self.started_at or self.created_at
        if base_time and self.estimated_hours:
            from datetime import timedelta
            hours = float(self.estimated_hours)
            return base_time + timedelta(hours=hours)
        return None


class TimeEntry(BaseModel):
    """Time tracking entry for tasks."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_entries')
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, related_name='time_entries')
    date = models.DateField()
    hours = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.1)])
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-created_at']
        unique_together = ['task', 'employee', 'date']

    def __str__(self):
        return f"{self.employee} - {self.task} - {self.date}"


class PersonnelRecommendation(BaseModel):
    """Lưu lịch sử đề xuất nhân sự cho dự án."""
    OPTIMIZATION_GOAL_CHOICES = [
        ('performance', 'Tối ưu hiệu suất'),
        ('cost', 'Tối ưu chi phí'),
        ('balanced', 'Cân bằng'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='personnel_recommendations')
    optimization_goal = models.CharField(
        max_length=20,
        choices=OPTIMIZATION_GOAL_CHOICES,
        default='balanced',
        help_text='Mục tiêu tối ưu hóa'
    )
    recommended_employees = models.ManyToManyField(
        'resources.Employee',
        through='PersonnelRecommendationDetail',
        related_name='recommendations',
        help_text='Danh sách nhân sự được đề xuất'
    )
    total_estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Tổng chi phí ước tính (VNĐ)'
    )
    reasoning = models.TextField(help_text='Lý do và phân tích đề xuất')
    is_applied = models.BooleanField(default=False, help_text='Đã áp dụng đề xuất này chưa')
    applied_at = models.DateTimeField(null=True, blank=True, help_text='Thời điểm áp dụng')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Đề xuất nhân sự'
        verbose_name_plural = 'Đề xuất nhân sự'

    def __str__(self):
        return f"{self.project.name} - {self.get_optimization_goal_display()} ({self.created_at.strftime('%d/%m/%Y')})"


class PersonnelRecommendationDetail(BaseModel):
    """Chi tiết đề xuất nhân sự (through model)."""
    recommendation = models.ForeignKey(PersonnelRecommendation, on_delete=models.CASCADE)
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE)
    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Tỷ lệ phân bổ (%)'
    )
    estimated_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text='Số giờ ước tính'
    )
    estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Chi phí ước tính (VNĐ)'
    )
    reasoning = models.TextField(blank=True, help_text='Lý do đề xuất nhân sự này')

    class Meta:
        unique_together = ['recommendation', 'employee']
        verbose_name = 'Chi tiết đề xuất nhân sự'
        verbose_name_plural = 'Chi tiết đề xuất nhân sự'

    def __str__(self):
        return f"{self.recommendation.project.name} - {self.employee.full_name} ({self.allocation_percentage}%)"
