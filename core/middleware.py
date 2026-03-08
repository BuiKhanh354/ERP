from django.contrib.auth import get_user_model, login
from django.utils.deprecation import MiddlewareMixin


class AutoLoginMiddleware(MiddlewareMixin):
    """
    Middleware dành riêng cho môi trường Dev/Test.
    Tự động đăng nhập (có session hợp lệ) bằng user đầu tiên có quyền superuser.
    Nếu chưa có superuser nào, sẽ tạo mới.
    Đồng thời đảm bảo user có UserProfile để tránh lỗi template.
    """

    def process_request(self, request):
        # Nếu user đã đăng nhập chuẩn (có session), bỏ qua
        if request.user.is_authenticated:
            return

        User = get_user_model()

        # Lấy superuser đầu tiên trong DB, hoặc tạo mới nếu chưa có
        user = User.objects.filter(is_superuser=True, is_active=True).first()
        if not user:
            user = User.objects.create_superuser(
                username='admin',
                email='admin@erp.local',
                password='admin123',
            )

        # Đảm bảo user có UserProfile (tránh lỗi template khi gọi user.profile)
        self._ensure_profile(user)

        # Gọi login() chuẩn của Django để tạo session hợp lệ
        login(request, user)

    @staticmethod
    def _ensure_profile(user):
        """Tạo UserProfile nếu chưa tồn tại."""
        from core.models import UserProfile
        if not hasattr(user, 'profile') or user.profile is None:
            try:
                user.profile
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(
                    user=user,
                    role=UserProfile.ROLE_MANAGER,
                )
