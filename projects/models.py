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
        help_text='NgÃ¢n sÃ¡ch dÃ nh cho nhÃ¢n sá»± (VNÄ)'
    )
    estimated_employees = models.PositiveIntegerField(default=0, help_text='Sá»‘ nhÃ¢n sá»± dá»± kiáº¿n cho dá»± Ã¡n')
    departments = models.ManyToManyField('resources.Department', related_name='projects', blank=True, help_text='PhÃ²ng ban phá»¥ trÃ¡ch dá»± Ã¡n')
    required_departments = models.ManyToManyField(
        'resources.Department',
        related_name='required_projects',
        blank=True,
        help_text='CÃ¡c phÃ²ng ban báº¯t buá»™c cáº§n tham gia dá»± Ã¡n'
    )
    project_manager = models.ForeignKey(
        'resources.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects',
        help_text='Project Manager chÃ­nh cá»§a dá»± Ã¡n'
    )
    delay_penalty_enabled = models.BooleanField(default=True, help_text='Bat/tat tinh nang phat KPI do tre han cho du an')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def calculated_progress(self):
        """TÃ­nh tiáº¿n Ä‘á»™ dá»± Ã¡n dá»±a trÃªn táº¥t cáº£ tasks."""
        tasks = self.tasks.all()
        if not tasks.exists():
            return 0
        return tasks.aggregate(avg=models.Avg('progress_percent'))['avg'] or 0


class ProjectPhase(BaseModel):
    """Giai Ä‘oáº¡n dá»± Ã¡n (Agile lifecycle phases)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='phases')
    phase_name = models.CharField(max_length=200, help_text='TÃªn giai Ä‘oáº¡n')
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    order_index = models.PositiveIntegerField(default=0, help_text='Thá»© tá»± sáº¯p xáº¿p')

    class Meta:
        ordering = ['order_index', 'created_at']
        verbose_name = 'Giai Ä‘oáº¡n dá»± Ã¡n'
        verbose_name_plural = 'Giai Ä‘oáº¡n dá»± Ã¡n'

    def __str__(self):
        return f"{self.project.name} - {self.phase_name}"

    @property
    def calculated_progress(self):
        """TÃ­nh tiáº¿n Ä‘á»™ phase dá»±a trÃªn tasks."""
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
        ('assigned', 'ÄÃ£ giao'),
        ('accepted', 'ÄÃ£ nháº­n'),
        ('in_progress', 'Äang thá»±c hiá»‡n'),
        ('completed', 'HoÃ n thÃ nh'),
        ('rejected', 'Tá»« chá»‘i'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Tháº¥p'),
        ('medium', 'Trung bÃ¬nh'),
        ('high', 'Cao'),
        ('critical', 'Kháº©n cáº¥p'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    phase = models.ForeignKey('ProjectPhase', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', help_text='Giai Ä‘oáº¡n dá»± Ã¡n')
    progress_percent = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Tiáº¿n Ä‘á»™ hoÃ n thÃ nh (0-100%)')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    required_skills = models.TextField(blank=True, default='', help_text='Ky nang yeu cau de hoan thanh task')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', help_text='Má»©c Ä‘á»™ Æ°u tiÃªn')
    department = models.ForeignKey('resources.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', help_text='PhÃ²ng ban phá»¥ trÃ¡ch cÃ´ng viá»‡c')
    assigned_to = models.ForeignKey('resources.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assignment_status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS_CHOICES, default='assigned', help_text='Tráº¡ng thÃ¡i giao/nháº­n viá»‡c')
    due_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    started_at = models.DateTimeField(null=True, blank=True, help_text='Thá»i Ä‘iá»ƒm báº¯t Ä‘áº§u tÃ­nh giá» Æ°á»›c tÃ­nh')
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
        """TÃ­nh thá»i Ä‘iá»ƒm káº¿t thÃºc Æ°á»›c tÃ­nh dá»±a trÃªn started_at hoáº·c created_at."""
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
    """LÆ°u lá»‹ch sá»­ Ä‘á» xuáº¥t nhÃ¢n sá»± cho dá»± Ã¡n."""
    OPTIMIZATION_GOAL_CHOICES = [
        ('performance', 'Tá»‘i Æ°u hiá»‡u suáº¥t'),
        ('cost', 'Tá»‘i Æ°u chi phÃ­'),
        ('balanced', 'CÃ¢n báº±ng'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='personnel_recommendations')
    optimization_goal = models.CharField(
        max_length=20,
        choices=OPTIMIZATION_GOAL_CHOICES,
        default='balanced',
        help_text='Má»¥c tiÃªu tá»‘i Æ°u hÃ³a'
    )
    recommended_employees = models.ManyToManyField(
        'resources.Employee',
        through='PersonnelRecommendationDetail',
        related_name='recommendations',
        help_text='Danh sÃ¡ch nhÃ¢n sá»± Ä‘Æ°á»£c Ä‘á» xuáº¥t'
    )
    total_estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Tá»•ng chi phÃ­ Æ°á»›c tÃ­nh (VNÄ)'
    )
    reasoning = models.TextField(help_text='LÃ½ do vÃ  phÃ¢n tÃ­ch Ä‘á» xuáº¥t')
    is_applied = models.BooleanField(default=False, help_text='ÄÃ£ Ã¡p dá»¥ng Ä‘á» xuáº¥t nÃ y chÆ°a')
    applied_at = models.DateTimeField(null=True, blank=True, help_text='Thá»i Ä‘iá»ƒm Ã¡p dá»¥ng')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Äá» xuáº¥t nhÃ¢n sá»±'
        verbose_name_plural = 'Äá» xuáº¥t nhÃ¢n sá»±'

    def __str__(self):
        return f"{self.project.name} - {self.get_optimization_goal_display()} ({self.created_at.strftime('%d/%m/%Y')})"


class PersonnelRecommendationDetail(BaseModel):
    """Chi tiáº¿t Ä‘á» xuáº¥t nhÃ¢n sá»± (through model)."""
    recommendation = models.ForeignKey(PersonnelRecommendation, on_delete=models.CASCADE)
    employee = models.ForeignKey('resources.Employee', on_delete=models.CASCADE)
    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Tá»· lá»‡ phÃ¢n bá»• (%)'
    )
    estimated_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text='Sá»‘ giá» Æ°á»›c tÃ­nh'
    )
    estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Chi phÃ­ Æ°á»›c tÃ­nh (VNÄ)'
    )
    reasoning = models.TextField(blank=True, help_text='LÃ½ do Ä‘á» xuáº¥t nhÃ¢n sá»± nÃ y')

    class Meta:
        unique_together = ['recommendation', 'employee']
        verbose_name = 'Chi tiáº¿t Ä‘á» xuáº¥t nhÃ¢n sá»±'
        verbose_name_plural = 'Chi tiáº¿t Ä‘á» xuáº¥t nhÃ¢n sá»±'

    def __str__(self):
        return f"{self.recommendation.project.name} - {self.employee.full_name} ({self.allocation_percentage}%)"



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
        ('pending', 'Chá»'),
        ('in_progress', 'Äang thá»±c hiá»‡n'),
        ('completed', 'HoÃ n thÃ nh'),
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
    """Lá»‹ch sá»­ cáº­p nháº­t tiáº¿n Ä‘á»™ cÃ´ng viá»‡c."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='progress_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='progress_logs')
    progress_percent = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Tiáº¿n Ä‘á»™ táº¡i thá»i Ä‘iá»ƒm cáº­p nháº­t')
    note = models.TextField(blank=True, help_text='Ghi chÃº tiáº¿n Ä‘á»™')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lá»‹ch sá»­ cáº­p nháº­t tiáº¿n Ä‘á»™'
        verbose_name_plural = 'Lá»‹ch sá»­ cáº­p nháº­t tiáº¿n Ä‘á»™'

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

