from django.db import models
from django.contrib.auth.models import User
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
    project_manager = models.ForeignKey(
        'resources.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects',
        help_text='Project Manager chính của dự án'
    )
    delay_penalty_enabled = models.BooleanField(default=True, help_text='Bat/tat tinh nang phat KPI do tre han cho du an')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def calculated_progress(self):
        """Tính tiến độ dự án dựa trên tất cả tasks."""
        tasks = self.tasks.all()
        if not tasks.exists():
            return 0
        return tasks.aggregate(avg=models.Avg('progress_percent'))['avg'] or 0


class ProjectPhase(BaseModel):
    """Giai đoạn dự án (Agile lifecycle phases)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='phases')
    phase_name = models.CharField(max_length=200, help_text='Tên giai đoạn')
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    order_index = models.PositiveIntegerField(default=0, help_text='Thứ tự sắp xếp')

    class Meta:
        ordering = ['order_index', 'created_at']
        verbose_name = 'Giai đoạn dự án'
        verbose_name_plural = 'Giai đoạn dự án'

    def __str__(self):
        return f"{self.project.name} - {self.phase_name}"

    @property
    def calculated_progress(self):
        """Tính tiến độ phase dựa trên tasks."""
        tasks = self.tasks.all()
        if not tasks.exists():
            return 0
        return tasks.aggregate(avg=models.Avg('progress_percent'))['avg'] or 0

    @property
    def task_count(self):
        return self.tasks.count()


class Task(BaseModel):
    """Task model for project tasks."""
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'Review'),
        ('done', 'Done'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    ASSIGNMENT_STATUS_CHOICES = [
        ('assigned', 'Đã giao'),
        ('accepted', 'Đã nhận'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('rejected', 'Từ chối'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Khẩn cấp'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    phase = models.ForeignKey('ProjectPhase', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', help_text='Giai đoạn dự án')
    progress_percent = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Tiến độ hoàn thành (0-100%)')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    required_skills = models.TextField(blank=True, default='', help_text='Ky nang yeu cau de hoan thanh task')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', help_text='Mức độ ưu tiên')
    department = models.ForeignKey('resources.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', help_text='Phòng ban phụ trách công việc')
    assigned_to = models.ForeignKey('resources.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assignees = models.ManyToManyField(
        'resources.Employee',
        blank=True,
        related_name='multi_assigned_tasks',
        help_text='Danh sach nhan su duoc giao task'
    )
    assignment_status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS_CHOICES, default='assigned', help_text='Trang thai giao/nhan viec')
    planned_start_date = models.DateField(null=True, blank=True, help_text='Ngay bat dau du kien')
    due_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    started_at = models.DateTimeField(null=True, blank=True, help_text='Thời điểm bắt đầu tính giờ ước tính')
    completed_at = models.DateTimeField(null=True, blank=True, help_text='Thoi diem hoan thanh task')
    days_late = models.IntegerField(default=0, help_text='So ngay tre han')
    DELAY_REASON_CHOICES = [
        ('self', 'Ca nhan'),
        ('dependency', 'Phu thuoc'),
        ('external', 'Ngoai canh'),
        ('scope_change', 'Doi pham vi'),
    ]
    delay_reason_type = models.CharField(max_length=20, choices=DELAY_REASON_CHOICES, default='self')
    approved_delay = models.BooleanField(default=False)
    delay_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delay_explanation = models.TextField(blank=True, default='')
    assignee_skills_snapshot = models.TextField(blank=True, default='', help_text='Snapshot ky nang nhan su khi nhan task')
    workload_snapshot = models.PositiveIntegerField(default=0, help_text='So task dang mo cua nhan su tai thoi diem gan/nhan')

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



class ProjectMembershipRequest(BaseModel):
    """Request to add employee to project from PM, reviewed by Admin."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='membership_requests')
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, related_name='membership_requests')
    requested_by = models.ForeignKey(
        'resources.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='requests_sent',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True, help_text='Ly do request')
    admin_response = models.TextField(blank=True, help_text='Admin response')

    class Meta:
        unique_together = ['project', 'employee', 'status']
        ordering = ['-created_at']
        verbose_name = 'Project membership request'
        verbose_name_plural = 'Project membership requests'

    def __str__(self):
        return f"{self.employee.full_name} -> {self.project.name} ({self.get_status_display()})"


class DelayRuleConfig(BaseModel):
    """Rule engine config cho tinh KPI/penalty tre han."""
    name = models.CharField(max_length=120, default='Default Delay Rules')
    is_active = models.BooleanField(default=True)
    requires_explanation_after_days = models.PositiveIntegerField(default=5)
    warning_penalty_level_threshold = models.PositiveIntegerField(default=2)
    no_delay_monthly_reward = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    early_completion_reward_min = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    early_completion_reward_max = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    overdeliver_reward = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    penalty_light = models.DecimalField(max_digits=6, decimal_places=2, default=5)
    penalty_medium = models.DecimalField(max_digits=6, decimal_places=2, default=10)
    penalty_heavy = models.DecimalField(max_digits=6, decimal_places=2, default=15)
    penalty_critical = models.DecimalField(max_digits=6, decimal_places=2, default=20)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Cau hinh rule tre han'
        verbose_name_plural = 'Cau hinh rule tre han'

    def __str__(self):
        return self.name

class Milestone(BaseModel):
    """Milestone cho project."""
    STATUS_CHOICES = [
        ('pending', 'Chờ'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'projects_milestone'
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class TaskProgressLog(BaseModel):
    """Lịch sử cập nhật tiến độ công việc."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='progress_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='progress_logs')
    progress_percent = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Tiến độ tại thời điểm cập nhật')
    note = models.TextField(blank=True, help_text='Ghi chú tiến độ')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lịch sử cập nhật tiến độ'
        verbose_name_plural = 'Lịch sử cập nhật tiến độ'

    def __str__(self):
        return f"{self.task.name} - {self.progress_percent}% ({self.created_at.strftime('%d/%m/%Y %H:%M')})"


class TaskHistory(BaseModel):
    """Lich su snapshot cua task theo tung su kien."""
    EVENT_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('status_changed', 'Status Changed'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history_entries')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    event_note = models.TextField(blank=True, default='')

    task_name_snapshot = models.CharField(max_length=200, blank=True, default='')
    task_description_snapshot = models.TextField(blank=True, default='')
    assigned_to = models.ForeignKey(
        'resources.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_history_entries'
    )
    required_skills_snapshot = models.TextField(blank=True, default='')
    employee_skills_snapshot = models.TextField(blank=True, default='')
    started_at_snapshot = models.DateTimeField(null=True, blank=True)
    due_date_snapshot = models.DateField(null=True, blank=True)
    completed_at_snapshot = models.DateTimeField(null=True, blank=True)
    status_snapshot = models.CharField(max_length=20, blank=True, default='')
    assignment_status_snapshot = models.CharField(max_length=20, blank=True, default='')
    delay_note_snapshot = models.TextField(blank=True, default='')
    workload_at_time = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task history'
        verbose_name_plural = 'Task histories'

    def __str__(self):
        return f"{self.task_id} - {self.event_type} - {self.created_at:%d/%m/%Y %H:%M}"


class TaskDelayScoreLog(BaseModel):
    """Audit log cho thay doi diem tru do tre han cua task."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='delay_score_logs')
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, related_name='delay_score_logs')
    old_delay_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    new_delay_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delta_delay_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, blank=True, default='')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_delay_score_logs')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task delay score log'
        verbose_name_plural = 'Task delay score logs'

    def __str__(self):
        return f"{self.task_id} - delta {self.delta_delay_score}"


class KPIAdjustmentRequest(BaseModel):
    """Yeu cau dieu chinh KPI: Manager de xuat, Admin phe duyet."""

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE, related_name='kpi_adjustment_requests')
    points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('-20')), MaxValueValidator(Decimal('20'))],
        help_text='So diem dieu chinh, am la tru them, duong la cong bu'
    )
    reason = models.TextField(help_text='Ly do de xuat dieu chinh KPI')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='kpi_adjustments_requested')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='kpi_adjustments_reviewed')
    review_note = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'KPI adjustment request'
        verbose_name_plural = 'KPI adjustment requests'

    def __str__(self):
        return f"{self.employee.full_name} {self.points} ({self.status})"

