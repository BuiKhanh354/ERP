from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import BaseModel


class Department(BaseModel):
    """Department model for organizational structure."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, default='', help_text='Mã phòng ban')
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', help_text='Phòng ban cha'
    )
    manager = models.ForeignKey(
        'Employee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_departments'
    )
    is_active = models.BooleanField(default=True, help_text='Trạng thái hoạt động')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def employee_count(self):
        """Số nhân viên trong phòng ban."""
        return self.employee_set.filter(is_active=True).count()

    def get_ancestors(self):
        """Trả về danh sách phòng ban cha (từ gần nhất đến gốc)."""
        ancestors = []
        current = self.parent
        visited = set()
        while current and current.pk not in visited:
            ancestors.append(current)
            visited.add(current.pk)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Trả về tất cả phòng ban con (đệ quy)."""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class Position(BaseModel):
    """Position/Role model for employee positions."""
    name = models.CharField(max_length=100, unique=True, help_text='Tên chức vụ')
    description = models.TextField(blank=True, help_text='Mô tả chức vụ')
    is_active = models.BooleanField(default=True, help_text='Chức vụ còn hoạt động')

    class Meta:
        ordering = ['name']
        verbose_name = 'Chức vụ'
        verbose_name_plural = 'Chức vụ'

    def __str__(self):
        return self.name


class Employee(BaseModel):
    """Employee model for human resources."""
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Toàn thời gian'),
        ('part_time', 'Bán thời gian'),
        ('contractor', 'Hợp đồng'),
        ('intern', 'Thực tập'),
    ]

    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.CharField(max_length=100, blank=True, help_text='Chức vụ (tự do hoặc chọn từ danh sách)')
    position_fk = models.ForeignKey('Position', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', help_text='Chức vụ từ danh sách')
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='full_time')
    hire_date = models.DateField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class ResourceAllocation(BaseModel):
    """Resource allocation for projects."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='allocations')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='allocations')
    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        unique_together = ['employee', 'project', 'start_date']

    def __str__(self):
        return f"{self.employee} - {self.project} ({self.allocation_percentage}%)"


class PayrollSchedule(BaseModel):
    """Lịch phát lương chung cho toàn bộ nhân viên."""
    PAYMENT_DAY_CHOICES = [(i, f'Ngày {i}') for i in range(1, 29)]  # Ngày 1-28
    
    payment_day = models.IntegerField(
        choices=PAYMENT_DAY_CHOICES,
        default=5,
        help_text='Ngày phát lương trong tháng (1-28)'
    )
    notes = models.TextField(blank=True, help_text='Ghi chú về lịch phát lương')
    is_active = models.BooleanField(default=True, help_text='Lịch phát lương đang hoạt động')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lịch phát lương'
        verbose_name_plural = 'Lịch phát lương'

    def __str__(self):
        return f"Lịch phát lương chung - Ngày {self.payment_day}"

    def get_next_payment_date(self):
        """Tính ngày phát lương tiếp theo."""
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        
        # Nếu chưa đến ngày phát lương tháng này
        if today.day < self.payment_day:
            next_date = today.replace(day=self.payment_day)
        else:
            # Đã qua ngày phát lương, hiển thị ngày tháng sau
            if today.month == 12:
                next_date = today.replace(year=today.year + 1, month=1, day=self.payment_day)
            else:
                next_date = today.replace(month=today.month + 1, day=self.payment_day)
        
        return next_date
    
    @classmethod
    def get_active_schedule(cls):
        """Lấy lịch phát lương đang hoạt động (chỉ có 1 record)."""
        return cls.objects.filter(is_active=True).first()


class EmployeeHourlyRate(BaseModel):
    """Lưu lịch sử mức lương/giờ của nhân sự theo tháng."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='hourly_rates')
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)], help_text='Tháng (1-12)')
    year = models.IntegerField(help_text='Năm')
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], help_text='Lương tháng (VNĐ)')
    working_hours_per_month = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)], help_text='Tổng số giờ làm việc trong tháng')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], help_text='Lương/giờ (VNĐ/giờ)')
    notes = models.TextField(blank=True, help_text='Ghi chú')

    class Meta:
        ordering = ['-year', '-month']
        unique_together = ['employee', 'month', 'year']
        verbose_name = 'Lương/giờ theo tháng'
        verbose_name_plural = 'Lương/giờ theo tháng'

    def __str__(self):
        return f"{self.employee.full_name} - {self.month}/{self.year}: {self.hourly_rate} VNĐ/giờ"

