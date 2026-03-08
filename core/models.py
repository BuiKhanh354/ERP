import random
import string

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class BaseModel(models.Model):
    """Base model với các trường chung cho mọi model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True


class PasswordResetOTP(BaseModel):
    """OTP đặt lại mật khẩu cho user."""

    EXPIRY_MINUTES = 10

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_otps")
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "otp_code", "is_used"]),
        ]
        ordering = ["-created_at"]

    @property
    def code(self):
        return self.otp_code

    def is_valid(self) -> bool:
        return (not self.is_used) and self.expires_at >= timezone.now()

    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()

    @classmethod
    def generate_otp(cls, user):
        """Tạo OTP 6 chữ số cho user."""
        code = ''.join(random.choices(string.digits, k=6))
        otp = cls(
            user=user,
            otp_code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES),
        )
        return otp


class Notification(BaseModel):
    """Thông báo cho từng user (dùng cho bell + modal)."""

    LEVEL_INFO = "info"
    LEVEL_SUCCESS = "success"
    LEVEL_WARNING = "warning"
    LEVEL_DANGER = "danger"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "Thông tin"),
        (LEVEL_SUCCESS, "Thành công"),
        (LEVEL_WARNING, "Cảnh báo"),
        (LEVEL_DANGER, "Khẩn cấp"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    url = models.CharField(max_length=500, blank=True, default="")
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["user", "level", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.user.username})"


class UserProfile(BaseModel):
    """Hồ sơ mở rộng cho user (avatar, role, ...)."""

    ROLE_MANAGER = "manager"
    ROLE_EMPLOYEE = "employee"
    ROLE_CHOICES = [
        (ROLE_MANAGER, "Quản lý"),
        (ROLE_EMPLOYEE, "Nhân viên"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_EMPLOYEE,
        help_text="Vai trò của người dùng trong hệ thống.",
    )
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_CHOICES = [
        (THEME_LIGHT, "Giao diện sáng"),
        (THEME_DARK, "Giao diện tối"),
    ]
    theme = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default=THEME_LIGHT,
        help_text="Tuỳ chọn giao diện của người dùng (light/dark).",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Profile: {self.user.username}"

    def is_manager(self) -> bool:
        """Kiểm tra user có phải quản lý không."""
        return self.role == self.ROLE_MANAGER

    def is_employee(self) -> bool:
        """Kiểm tra user có phải nhân viên không."""
        return self.role == self.ROLE_EMPLOYEE


class EmailChangeOTP(BaseModel):
    """OTP xác nhận đổi email trong trang Hồ sơ."""

    EXPIRY_MINUTES = 10

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_change_otps")
    new_email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "new_email", "otp_code", "is_used"]),
            models.Index(fields=["user", "is_used", "created_at"]),
        ]

    @property
    def code(self):
        return self.otp_code

    def is_valid(self) -> bool:
        return (not self.is_used) and self.expires_at >= timezone.now()

    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()

    @classmethod
    def generate_otp(cls, user, new_email):
        """Tạo OTP 6 chữ số cho đổi email."""
        code = ''.join(random.choices(string.digits, k=6))
        otp = cls(
            user=user,
            new_email=new_email,
            otp_code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES),
        )
        return otp


class AccountDeleteOTP(BaseModel):
    """OTP xác nhận xoá tài khoản."""

    EXPIRY_MINUTES = 10

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_delete_otps")
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "otp_code", "is_used"]),
            models.Index(fields=["user", "is_used", "created_at"]),
        ]

    @property
    def code(self):
        return self.otp_code

    def is_valid(self) -> bool:
        return (not self.is_used) and self.expires_at >= timezone.now()

    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()

    @classmethod
    def generate_otp(cls, user):
        """Tạo OTP 6 chữ số cho xoá tài khoản."""
        code = ''.join(random.choices(string.digits, k=6))
        otp = cls(
            user=user,
            otp_code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES),
        )
        return otp


class AIChatHistory(BaseModel):
    """Lịch sử chat AI cho người dùng."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_chat_history')
    message = models.TextField()
    response = models.TextField()
    session_id = models.CharField(max_length=100, db_index=True, help_text='Mã phiên để nhóm các tin nhắn')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'session_id']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at}"


# =============================================
# RBAC Models (Role-Based Access Control)
# =============================================

class Role(models.Model):
    """Role trong hệ thống RBAC."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        ordering = ['name']

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Permission trong hệ thống RBAC."""
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    module = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permissions'
        ordering = ['module', 'code']

    def __str__(self):
        return f"{self.module}.{self.code}" if self.module else self.code


class UserRole(models.Model):
    """Liên kết User với Role."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        db_table = 'user_roles'
        unique_together = ['user', 'role']

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class RolePermission(models.Model):
    """Liên kết Role với Permission."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')

    class Meta:
        db_table = 'role_permissions'
        unique_together = ['role', 'permission']

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class AuditLog(models.Model):
    """System audit log - theo dõi mọi thay đổi quan trọng."""
    ACTION_CHOICES = [
        ('CREATE', 'Tạo mới'),
        ('UPDATE', 'Cập nhật'),
        ('DELETE', 'Xóa'),
        ('APPROVE', 'Phê duyệt'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    table_name = models.CharField(max_length=200)
    record_id = models.CharField(max_length=100, blank=True, default='')
    old_data = models.TextField(null=True, blank=True)
    new_data = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_auditlog'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} on {self.table_name} by {self.user}"

