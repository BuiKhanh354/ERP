from django.urls import path
from . import views
from .analytics_views import AnalyticsView
from . import ai_chat_views
from . import ai_insights_views

app_name = "core"

urlpatterns = [
    # Auth
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("otp-verify/", views.OTPVerifyView.as_view(), name="otp-verify"),

    # Dashboard (yêu cầu đăng nhập)
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),

    # Notifications (JSON)
    path("notifications/", views.NotificationsListView.as_view(), name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        views.NotificationMarkReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notifications/mark-all-read/",
        views.NotificationMarkAllReadView.as_view(),
        name="notification-mark-all-read",
    ),

    # Profile / Account
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("change-password-required/", views.ChangePasswordRequiredView.as_view(), name="change-password-required"),
    
    # AI Chat
    path("ai-chat/", ai_chat_views.AIChatView.as_view(), name="ai-chat"),
    path("api/ai-chat/", ai_chat_views.AIChatAPIView.as_view(), name="ai-chat-api"),
    path("ai-chat/history/", ai_chat_views.AIChatHistoryView.as_view(), name="ai-chat-history"),
    path("api/ai-chat/delete/", ai_chat_views.AIChatDeleteView.as_view(), name="ai-chat-delete"),
    
    # AI Insights
    path("ai/sales-analysis/", ai_insights_views.SalesAnalysisView.as_view(), name="ai-sales-analysis"),
    path("ai/purchasing-analysis/", ai_insights_views.PurchasingAnalysisView.as_view(), name="ai-purchasing-analysis"),
    path("ai/expense-optimization/", ai_insights_views.ExpenseOptimizationView.as_view(), name="ai-expense-optimization"),
    path("ai/salary-recommendation/", ai_insights_views.SalaryRecommendationView.as_view(), name="ai-salary-recommendation"),
    
    # AI Insights API
    path("api/ai/sales-analysis/", ai_insights_views.AISalesAnalysisAPIView.as_view(), name="ai-sales-analysis-api"),
    path("api/ai/purchasing-analysis/", ai_insights_views.AIPurchasingAnalysisAPIView.as_view(), name="ai-purchasing-analysis-api"),
    path("api/ai/expense-optimization/", ai_insights_views.AIExpenseOptimizationAPIView.as_view(), name="ai-expense-optimization-api"),
    path("api/ai/salary-recommendation/", ai_insights_views.AISalaryRecommendationAPIView.as_view(), name="ai-salary-recommendation-api"),
]

