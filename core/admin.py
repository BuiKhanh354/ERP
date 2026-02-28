from django.contrib import admin
from .models import Notification, UserProfile, EmailChangeOTP, AccountDeleteOTP, AIChatHistory


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "level", "is_read", "created_at")
    list_filter = ("level", "is_read", "created_at")
    search_fields = ("title", "message", "user__username", "user__email")
    ordering = ("-created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "theme", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-created_at",)


@admin.register(EmailChangeOTP)
class EmailChangeOTPAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "new_email", "otp_code", "is_used", "expires_at", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("user__username", "user__email", "new_email", "otp_code")
    ordering = ("-created_at",)


@admin.register(AccountDeleteOTP)
class AccountDeleteOTPAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "otp_code", "is_used", "expires_at", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("user__username", "user__email", "otp_code")
    ordering = ("-created_at",)


@admin.register(AIChatHistory)
class AIChatHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message_preview", "response_preview", "session_id", "created_at")
    list_filter = ("created_at", "session_id")
    search_fields = ("user__username", "user__email", "message", "response", "session_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Tin nhắn'
    
    def response_preview(self, obj):
        return obj.response[:50] + '...' if len(obj.response) > 50 else obj.response
    response_preview.short_description = 'Phản hồi'
