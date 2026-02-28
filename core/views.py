from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, FormView
from django.http import JsonResponse, HttpResponseBadRequest
from django.views import View
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from email.mime.image import MIMEImage
import os

from .forms import (
    LoginForm,
    ForgotPasswordForm,
    OTPVerifyForm,
    ProfileUpdateForm,
    EmailChangeRequestForm,
    EmailChangeVerifyForm,
    PasswordChangeWithOldForm,
    RequiredPasswordChangeForm,
)
from .models import (
    PasswordResetOTP,
    Notification,
    UserProfile,
    EmailChangeOTP,
    AccountDeleteOTP,
)


User = get_user_model()


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard chính, yêu cầu đăng nhập trước."""

    template_name = "pages/dashboard.html"
    login_url = reverse_lazy("core:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .services import DashboardService
        import json
        stats = DashboardService.get_dashboard_stats(self.request.user)
        context.update(stats)
        # Thêm data cho chart chi tiêu (JSON string để dùng trong template)
        expense_data = stats.get('monthly_expense_data', {
            'labels': [],
            'actual': [],
            'budget': []
        })
        context['expense_chart_data'] = json.dumps(expense_data)
        return context


class LoginView(DjangoLoginView):
    """Trang đăng nhập ERP với giao diện tùy biến."""

    template_name = "pages/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Xử lý sau khi login thành công."""
        user = form.get_user()
        
        # Kiểm tra xem có cần đổi mật khẩu không (mật khẩu mặc định)
        if self.request.session.get('require_password_change'):
            # Login user trước
            login(self.request, user)
            # Xóa flag trong session
            del self.request.session['require_password_change']
            # Redirect đến trang đổi mật khẩu bắt buộc
            return redirect('core:change-password-required')
        
        # Login bình thường
        return super().form_valid(form)


class LogoutView(TemplateView):
    """Đăng xuất và chuyển về trang login."""

    def get(self, request, *args, **kwargs):
        # Kiểm tra xem user đang ở admin panel hay client site
        is_admin_panel = False
        if hasattr(request, 'resolver_match') and request.resolver_match:
            is_admin_panel = 'admin_custom' in request.resolver_match.namespace
        if not is_admin_panel:
            is_admin_panel = 'admin-panel' in request.path or request.path.startswith('/admin-panel/')
        
        logout(request)
        messages.success(request, "Bạn đã đăng xuất khỏi hệ thống.")
        
        # Nếu đang ở admin panel, redirect về admin login, ngược lại về client login
        if is_admin_panel:
            return redirect("admin:login")
        return redirect("core:login")


class ForgotPasswordView(FormView):
    """Nhập email để gửi OTP quên mật khẩu."""

    template_name = "pages/forgot_password.html"
    form_class = ForgotPasswordForm
    success_url = reverse_lazy("core:otp-verify")

    def form_valid(self, form):
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.get(email__iexact=email)

        # Tạo OTP
        otp = PasswordResetOTP.generate_otp(user)
        otp.save()

        # Gửi email OTP
        try:
            subject = "Mã OTP đặt lại mật khẩu - ERP System"
            html_message = render_to_string(
                "emails/password_reset_otp.html",
                {
                    "user": user,
                    "otp": otp.code,
                    "expires_in_minutes": PasswordResetOTP.EXPIRY_MINUTES,
                    "app_name": "ERP System",
                },
            )
            plain_message = strip_tags(html_message)

            email_msg = EmailMultiAlternatives(
                subject, plain_message, settings.DEFAULT_FROM_EMAIL, [user.email]
            )
            email_msg.attach_alternative(html_message, "text/html")

            # Attach logo
            logo_path = os.path.join(settings.BASE_DIR, "static", "assets", "logo", "logo.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo = MIMEImage(f.read())
                    logo.add_header("Content-ID", "<erp-logo>")
                    logo.add_header("Content-Disposition", "inline", filename="logo.png")
                    email_msg.attach(logo)

            email_msg.send()

            messages.success(
                self.request,
                f"Mã OTP đã được gửi đến email {user.email}. Vui lòng kiểm tra hộp thư.",
            )
        except Exception as e:
            messages.error(
                self.request,
                f"Không thể gửi email OTP. Vui lòng thử lại sau. Lỗi: {str(e)}",
            )
            return self.form_invalid(form)

        # Lưu user_id vào session để dùng trong OTPVerifyView
        self.request.session["password_reset_user_id"] = user.id
        return super().form_valid(form)


class OTPVerifyView(FormView):
    """Xác thực OTP và đặt lại mật khẩu mới."""

    template_name = "pages/otp_verify.html"
    form_class = OTPVerifyForm
    success_url = reverse_lazy("core:login")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user_id = self.request.session.get("password_reset_user_id")
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                kwargs["user"] = user
            except User.DoesNotExist:
                pass
        return kwargs

    def form_valid(self, form):
        user_id = self.request.session.get("password_reset_user_id")
        if not user_id:
            messages.error(self.request, "Phiên làm việc đã hết hạn. Vui lòng thử lại.")
            return redirect("core:forgot-password")

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            messages.error(self.request, "Người dùng không tồn tại.")
            return redirect("core:forgot-password")

        otp_code = form.cleaned_data["otp"]
        otp_obj = PasswordResetOTP.objects.filter(
            user=user, code=otp_code, is_used=False
        ).first()

        if not otp_obj or otp_obj.is_expired():
            messages.error(self.request, "Mã OTP không hợp lệ hoặc đã hết hạn.")
            return self.form_invalid(form)

        # Đặt lại mật khẩu
        new_password = form.cleaned_data["new_password1"]
        user.set_password(new_password)
        user.save()

        # Đánh dấu OTP đã dùng
        otp_obj.is_used = True
        otp_obj.save()

        # Xóa user_id khỏi session
        del self.request.session["password_reset_user_id"]

        messages.success(
            self.request, "Đã đặt lại mật khẩu thành công. Vui lòng đăng nhập lại."
        )
        return super().form_valid(form)


class ChangePasswordRequiredView(LoginRequiredMixin, FormView):
    """Trang đổi mật khẩu bắt buộc cho user mới tạo."""

    template_name = "pages/change_password_required.html"
    form_class = RequiredPasswordChangeForm
    login_url = reverse_lazy("core:login")

    def dispatch(self, request, *args, **kwargs):
        # Kiểm tra xem user có đang dùng mật khẩu mặc định không
        if not request.user.check_password('12345678'):
            # Nếu đã đổi mật khẩu rồi, redirect về dashboard
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Xử lý đổi mật khẩu thành công."""
        # Lưu mật khẩu mới
        form.save()
        
        # Cập nhật session để không bị logout
        update_session_auth_hash(self.request, self.request.user)
        
        messages.success(
            self.request,
            "Đã đổi mật khẩu thành công. Bạn có thể sử dụng hệ thống."
        )
        
        # Redirect về dashboard
        return redirect('core:dashboard')


class ProfileView(LoginRequiredMixin, TemplateView):
    """Trang hồ sơ cá nhân."""

    template_name = "pages/profile.html"
    login_url = reverse_lazy("core:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["user"] = user
        try:
            context["profile"] = user.profile
        except:
            from .models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            context["profile"] = profile

        # OTP đổi email đang chờ (nếu có)
        from .models import EmailChangeOTP
        pending = (
            EmailChangeOTP.objects.filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )
        context["has_pending_email_change"] = bool(pending)
        context["pending_new_email"] = pending.new_email if pending else None
        context["pending_expires_at"] = pending.expires_at if pending else None

        return context

    def _is_ajax(self, request):
        """Check if request is AJAX"""
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _json_response(self, success, message, errors=None, redirect_url=None):
        """Return JSON response for AJAX requests"""
        data = {"success": success, "message": message}
        if errors:
            data["errors"] = errors
        if redirect_url:
            data["redirect_url"] = redirect_url
        return JsonResponse(data)

    def post(self, request, *args, **kwargs):
        """Xử lý các action từ form (update profile, change password, request email change, etc.)"""
        action = request.POST.get("action")

        if action == "update_profile":
            form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
            if form.is_valid():
                form.save()
                if self._is_ajax(request):
                    return self._json_response(
                        True, "Đã cập nhật thông tin thành công."
                    )
                messages.success(request, "Đã cập nhật thông tin thành công.")
                return redirect("core:profile")
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra khi cập nhật.")
                return self.get(request, *args, **kwargs)

        elif action == "change_password":
            form = PasswordChangeWithOldForm(request.POST, user=request.user)
            if form.is_valid():
                new_password = form.cleaned_data["new_password1"]
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                if self._is_ajax(request):
                    return self._json_response(
                        True,
                        "Đã đổi mật khẩu thành công.",
                        redirect_url=str(reverse_lazy("core:login")),
                    )
                messages.success(request, "Đã đổi mật khẩu thành công.")
                return redirect("core:login")
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra khi đổi mật khẩu.")
                return self.get(request, *args, **kwargs)

        elif action == "request_email_change":
            form = EmailChangeRequestForm(request.POST, user=request.user)
            if form.is_valid():
                new_email = form.cleaned_data["new_email"]
                from .models import EmailChangeOTP

                # Tạo OTP
                otp = EmailChangeOTP.generate_otp(request.user, new_email)
                otp.save()

                # Gửi email OTP
                try:
                    subject = "Mã OTP xác nhận đổi email - PRM System"
                    html_message = render_to_string(
                        "emails/email_change_otp.html",
                        {
                            "user": request.user,
                            "otp": otp.code,
                            "new_email": new_email,
                            "expires_in_minutes": EmailChangeOTP.EXPIRY_MINUTES,
                            "app_name": "PRM System",
                        },
                    )
                    plain_message = strip_tags(html_message)

                    email_msg = EmailMultiAlternatives(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [new_email],
                    )
                    email_msg.attach_alternative(html_message, "text/html")

                    # Attach logo
                    logo_path = os.path.join(
                        settings.BASE_DIR, "static", "assets", "logo", "logo.png"
                    )
                    if os.path.exists(logo_path):
                        with open(logo_path, "rb") as f:
                            logo = MIMEImage(f.read())
                            logo.add_header("Content-ID", "<erp-logo>")
                            logo.add_header(
                                "Content-Disposition", "inline", filename="logo.png"
                            )
                            email_msg.attach(logo)

                    email_msg.send()

                    if self._is_ajax(request):
                        return self._json_response(
                            True,
                            f"Mã OTP đã được gửi đến email {new_email}. Vui lòng kiểm tra hộp thư.",
                        )
                    messages.success(
                        request,
                        f"Mã OTP đã được gửi đến email {new_email}. Vui lòng kiểm tra hộp thư.",
                    )
                except Exception as e:
                    if self._is_ajax(request):
                        return self._json_response(
                            False, f"Không thể gửi email OTP. Lỗi: {str(e)}"
                        )
                    messages.error(
                        request, f"Không thể gửi email OTP. Vui lòng thử lại sau."
                    )
                return self.get(request, *args, **kwargs)
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra.")
                return self.get(request, *args, **kwargs)

        elif action == "verify_email_change":
            form = EmailChangeVerifyForm(request.POST)
            if form.is_valid():
                otp_code = form.cleaned_data["otp"]
                from .models import EmailChangeOTP

                otp_obj = EmailChangeOTP.objects.filter(
                    user=request.user, code=otp_code, is_used=False
                ).first()

                if not otp_obj or otp_obj.is_expired():
                    if self._is_ajax(request):
                        return self._json_response(
                            False, "Mã OTP không hợp lệ hoặc đã hết hạn."
                        )
                    messages.error(
                        request, "Mã OTP không hợp lệ hoặc đã hết hạn."
                    )
                    return self.get(request, *args, **kwargs)

                # Đổi email
                request.user.email = otp_obj.new_email
                request.user.save()

                # Đánh dấu OTP đã dùng
                otp_obj.is_used = True
                otp_obj.save()

                if self._is_ajax(request):
                    return self._json_response(
                        True, f"Đã đổi email thành công thành {otp_obj.new_email}."
                    )
                messages.success(
                    request, f"Đã đổi email thành công thành {otp_obj.new_email}."
                )
                return self.get(request, *args, **kwargs)
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra.")
                return self.get(request, *args, **kwargs)

        elif action == "request_account_delete":
            from .models import AccountDeleteOTP

            # Kiểm tra xem đã có OTP đang chờ chưa
            pending = AccountDeleteOTP.objects.filter(
                user=request.user, is_used=False
            ).first()
            if pending and not pending.is_expired():
                if self._is_ajax(request):
                    return self._json_response(
                        False,
                        f"Đã có mã OTP đang chờ. Vui lòng kiểm tra email {request.user.email}.",
                    )
                messages.warning(
                    request,
                    f"Đã có mã OTP đang chờ. Vui lòng kiểm tra email {request.user.email}.",
                )
                return self.get(request, *args, **kwargs)

            # Tạo OTP mới
            otp = AccountDeleteOTP.generate_otp(request.user)
            otp.save()

            # Gửi email OTP
            try:
                subject = "Mã OTP xác nhận xoá tài khoản - PRM System"
                html_message = render_to_string(
                    "emails/account_delete_otp.html",
                    {
                        "user": request.user,
                        "otp": otp.code,
                        "expires_in_minutes": AccountDeleteOTP.EXPIRY_MINUTES,
                        "app_name": "PRM System",
                    },
                )
                plain_message = strip_tags(html_message)

                email_msg = EmailMultiAlternatives(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email],
                )
                email_msg.attach_alternative(html_message, "text/html")

                # Attach logo
                logo_path = os.path.join(
                    settings.BASE_DIR, "static", "assets", "logo", "logo.png"
                )
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        logo = MIMEImage(f.read())
                        logo.add_header("Content-ID", "<erp-logo>")
                        logo.add_header(
                            "Content-Disposition", "inline", filename="logo.png"
                        )
                        email_msg.attach(logo)

                email_msg.send()

                if self._is_ajax(request):
                    return self._json_response(
                        True,
                        f"Mã OTP đã được gửi đến email {request.user.email}. Vui lòng kiểm tra hộp thư.",
                    )
                messages.success(
                    request,
                    f"Mã OTP đã được gửi đến email {request.user.email}. Vui lòng kiểm tra hộp thư.",
                )
            except Exception as e:
                if self._is_ajax(request):
                    return self._json_response(
                        False, f"Không thể gửi email OTP. Lỗi: {str(e)}"
                    )
                messages.error(
                    request, "Không thể gửi email OTP. Vui lòng thử lại sau."
                )
            return self.get(request, *args, **kwargs)

        elif action == "verify_account_delete":
            form = EmailChangeVerifyForm(request.POST)
            if form.is_valid():
                otp_code = form.cleaned_data["otp"]
                from .models import AccountDeleteOTP

                otp_obj = AccountDeleteOTP.objects.filter(
                    user=request.user, code=otp_code, is_used=False
                ).first()

                if not otp_obj or otp_obj.is_expired():
                    if self._is_ajax(request):
                        return self._json_response(
                            False, "Mã OTP không hợp lệ hoặc đã hết hạn."
                        )
                    messages.error(
                        request, "Mã OTP không hợp lệ hoặc đã hết hạn."
                    )
                    return self.get(request, *args, **kwargs)

                # Đánh dấu OTP đã dùng
                otp_obj.is_used = True
                otp_obj.save()

                # Xóa tài khoản
                user_email = request.user.email
                request.user.delete()

                if self._is_ajax(request):
                    return self._json_response(
                        True,
                        "Đã xóa tài khoản thành công.",
                        redirect_url=str(reverse_lazy("core:login")),
                    )
                messages.success(request, "Đã xóa tài khoản thành công.")
                return redirect("core:login")
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra.")
                return self.get(request, *args, **kwargs)

        return HttpResponseBadRequest("Invalid action")


class NotificationsListView(LoginRequiredMixin, View):
    """Trả về danh sách thông báo của user hiện tại (JSON) để render modal bell."""

    login_url = reverse_lazy("core:login")

    def get(self, request, *args, **kwargs):
        limit = int(request.GET.get("limit", "30") or "30")
        limit = max(1, min(limit, 100))

        qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:limit]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

        items = []
        for n in qs:
            items.append(
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "level": n.level,
                    "url": n.url,
                    "is_read": n.is_read,
                    "created_at": n.created_at.strftime("%d/%m/%Y %H:%M"),
                }
            )

        return JsonResponse({"unread_count": unread_count, "items": items})


class NotificationMarkReadView(LoginRequiredMixin, View):
    """Đánh dấu đã đọc và trả về URL để điều hướng (JSON)."""

    login_url = reverse_lazy("core:login")

    def post(self, request, *args, **kwargs):
        notification_id = kwargs.get("pk")
        n = get_object_or_404(Notification, pk=notification_id, user=request.user)
        if not n.is_read:
            n.is_read = True
            n.save(update_fields=["is_read", "updated_at"])
        return JsonResponse({"ok": True, "url": n.url or ""})


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """Đánh dấu tất cả thông báo là đã đọc (JSON)."""

    login_url = reverse_lazy("core:login")

    def post(self, request, *args, **kwargs):
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, updated_at=timezone.now())
        
        return JsonResponse({
            "ok": True,
            "message": f"Đã đánh dấu {updated_count} thông báo là đã đọc.",
            "updated_count": updated_count
        })


class SettingsView(LoginRequiredMixin, TemplateView):
    """Trang Cài đặt tài khoản (theme + xoá tài khoản bằng OTP)."""

    template_name = "pages/settings.html"
    login_url = reverse_lazy("core:login")

    def _get_profile(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self._get_profile()
        context["profile"] = profile

        # OTP xoá tài khoản đang chờ (nếu có)
        pending = (
            AccountDeleteOTP.objects.filter(user=self.request.user, is_used=False)
            .order_by("-created_at")
            .first()
        )
        context["has_pending_delete_otp"] = bool(pending)
        context["pending_delete_expires_at"] = pending.expires_at if pending else None
        return context

    def _is_ajax(self, request):
        """Check if request is AJAX"""
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _json_response(self, success, message, errors=None, redirect_url=None):
        """Return JSON response for AJAX requests"""
        data = {"success": success, "message": message}
        if errors:
            data["errors"] = errors
        if redirect_url:
            data["redirect_url"] = redirect_url
        return JsonResponse(data)

    def post(self, request, *args, **kwargs):
        """Xử lý các action từ form (change theme, request delete OTP, verify delete OTP)"""
        action = request.POST.get("action")

        if action == "change_theme":
            profile = self._get_profile()
            new_theme = request.POST.get("theme")
            if new_theme in [UserProfile.THEME_LIGHT, UserProfile.THEME_DARK]:
                profile.theme = new_theme
                profile.save()
                if self._is_ajax(request):
                    return self._json_response(
                        True, f"Đã chuyển sang giao diện {profile.get_theme_display()}."
                    )
                messages.success(
                    request, f"Đã chuyển sang giao diện {profile.get_theme_display()}."
                )
            else:
                if self._is_ajax(request):
                    return self._json_response(False, "Theme không hợp lệ.")
                messages.error(request, "Theme không hợp lệ.")
            return self.get(request, *args, **kwargs)

        elif action == "request_account_delete":
            # Kiểm tra xem đã có OTP đang chờ chưa
            pending = AccountDeleteOTP.objects.filter(
                user=request.user, is_used=False
            ).first()
            if pending and not pending.is_expired():
                if self._is_ajax(request):
                    return self._json_response(
                        False,
                        f"Đã có mã OTP đang chờ. Vui lòng kiểm tra email {request.user.email}.",
                    )
                messages.warning(
                    request,
                    f"Đã có mã OTP đang chờ. Vui lòng kiểm tra email {request.user.email}.",
                )
                return self.get(request, *args, **kwargs)

            # Tạo OTP mới
            otp = AccountDeleteOTP.generate_otp(request.user)
            otp.save()

            # Gửi email OTP
            try:
                subject = "Mã OTP xác nhận xoá tài khoản - PRM System"
                html_message = render_to_string(
                    "emails/account_delete_otp.html",
                    {
                        "user": request.user,
                        "otp": otp.code,
                        "expires_in_minutes": AccountDeleteOTP.EXPIRY_MINUTES,
                        "app_name": "PRM System",
                    },
                )
                plain_message = strip_tags(html_message)

                email_msg = EmailMultiAlternatives(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email],
                )
                email_msg.attach_alternative(html_message, "text/html")

                # Attach logo
                logo_path = os.path.join(
                    settings.BASE_DIR, "static", "assets", "logo", "logo.png"
                )
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        logo = MIMEImage(f.read())
                        logo.add_header("Content-ID", "<erp-logo>")
                        logo.add_header(
                            "Content-Disposition", "inline", filename="logo.png"
                        )
                        email_msg.attach(logo)

                email_msg.send()

                if self._is_ajax(request):
                    return self._json_response(
                        True,
                        f"Mã OTP đã được gửi đến email {request.user.email}. Vui lòng kiểm tra hộp thư.",
                    )
                messages.success(
                    request,
                    f"Mã OTP đã được gửi đến email {request.user.email}. Vui lòng kiểm tra hộp thư.",
                )
            except Exception as e:
                if self._is_ajax(request):
                    return self._json_response(
                        False, f"Không thể gửi email OTP. Lỗi: {str(e)}"
                    )
                messages.error(
                    request, "Không thể gửi email OTP. Vui lòng thử lại sau."
                )
            return self.get(request, *args, **kwargs)

        elif action == "verify_account_delete":
            from .forms import EmailChangeVerifyForm

            form = EmailChangeVerifyForm(request.POST)
            if form.is_valid():
                otp_code = form.cleaned_data["otp"]
                otp_obj = AccountDeleteOTP.objects.filter(
                    user=request.user, code=otp_code, is_used=False
                ).first()

                if not otp_obj or otp_obj.is_expired():
                    if self._is_ajax(request):
                        return self._json_response(
                            False, "Mã OTP không hợp lệ hoặc đã hết hạn."
                        )
                    messages.error(
                        request, "Mã OTP không hợp lệ hoặc đã hết hạn."
                    )
                    return self.get(request, *args, **kwargs)

                # Đánh dấu OTP đã dùng
                otp_obj.is_used = True
                otp_obj.save()

                # Xóa tài khoản
                user_email = request.user.email
                request.user.delete()

                if self._is_ajax(request):
                    return self._json_response(
                        True,
                        "Đã xóa tài khoản thành công.",
                        redirect_url=str(reverse_lazy("core:login")),
                    )
                messages.success(request, "Đã xóa tài khoản thành công.")
                return redirect("core:login")
            else:
                if self._is_ajax(request):
                    return self._json_response(
                        False, "Có lỗi xảy ra.", errors=form.errors
                    )
                messages.error(request, "Có lỗi xảy ra.")
                return self.get(request, *args, **kwargs)

        return HttpResponseBadRequest("Invalid action")
