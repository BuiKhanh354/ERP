from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class LoginForm(AuthenticationForm):
    """Form đăng nhập cho phép dùng username hoặc email."""

    username = forms.CharField(
        label="Email hoặc Tên đăng nhập",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email hoặc tên đăng nhập",
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Mật khẩu",
                "autocomplete": "current-password",
            }
        ),
    )

    def clean(self):
        """Ghi đè logic xác thực để hỗ trợ đăng nhập bằng email."""
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            user = authenticate(self.request, username=username, password=password)

            # Nếu đăng nhập bằng email thất bại (hoặc user nhập email), thử map sang username
            if user is None and "@" in username:
                try:
                    user_obj = User.objects.get(email__iexact=username)
                    user = authenticate(
                        self.request,
                        username=user_obj.username,
                        password=password,
                    )
                except User.DoesNotExist:
                    user = None

            if user is None:
                raise forms.ValidationError(
                    "Vui lòng nhập đúng Email/Tên đăng nhập và mật khẩu. "
                    "Lưu ý thông tin đăng nhập có phân biệt chữ hoa/chữ thường.",
                    code="invalid_login",
                )

            self.confirm_login_allowed(user)
            
            # Kiểm tra mật khẩu mặc định (12345678)
            # Nếu user đăng nhập với mật khẩu mặc định, lưu vào session để redirect đến trang đổi mật khẩu
            if user.check_password('12345678'):
                self.request.session['require_password_change'] = True
                self.request.session['user_id_for_password_change'] = user.id
            
            self.user_cache = user

        return self.cleaned_data


class ForgotPasswordForm(forms.Form):
    """Form yêu cầu OTP quên mật khẩu theo email."""

    email = forms.EmailField(
        label="Email tài khoản",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập email đăng ký tài khoản",
        }),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email không tồn tại trong hệ thống.")
        return email


class OTPVerifyForm(SetPasswordForm):
    """Form nhập OTP và đặt lại mật khẩu mới."""

    otp = forms.CharField(
        label="Mã OTP",
        max_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập mã OTP gồm 6 số",
        }),
    )


class ProfileUpdateForm(forms.ModelForm):
    """Cập nhật tên + avatar (email đổi qua flow OTP riêng)."""

    avatar = forms.ImageField(
        label="Ảnh đại diện",
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Họ"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Tên"}
            ),
        }
        labels = {
            "first_name": "Họ",
            "last_name": "Tên",
        }


class EmailChangeRequestForm(forms.Form):
    new_email = forms.EmailField(
        label="Email mới",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Nhập email mới"}
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        email = self.cleaned_data["new_email"].strip().lower()
        if self.user and self.user.email and self.user.email.lower() == email:
            raise forms.ValidationError("Email mới phải khác email hiện tại.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng bởi tài khoản khác.")
        return email


class EmailChangeVerifyForm(forms.Form):
    otp = forms.CharField(
        label="Mã OTP",
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nhập mã OTP gồm 6 số",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )


class PasswordChangeWithOldForm(forms.Form):
    old_password = forms.CharField(
        label="Mật khẩu hiện tại",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Mật khẩu hiện tại"}
        ),
    )
    new_password1 = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Mật khẩu mới"}
        ),
    )
    new_password2 = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Nhập lại mật khẩu mới"}
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        pw = self.cleaned_data.get("old_password") or ""
        if self.user and (not self.user.check_password(pw)):
            raise forms.ValidationError("Mật khẩu hiện tại không đúng.")
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Mật khẩu mới và xác nhận mật khẩu không khớp.")
        if self.user and p1:
            try:
                validate_password(p1, self.user)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        return cleaned


class RequiredPasswordChangeForm(forms.Form):
    """Form đổi mật khẩu bắt buộc cho user mới tạo."""
    
    new_password1 = forms.CharField(
        label="Mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Mật khẩu mới",
                "autocomplete": "new-password"
            }
        ),
        help_text="Mật khẩu phải có ít nhất 8 ký tự."
    )
    new_password2 = forms.CharField(
        label="Xác nhận mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nhập lại mật khẩu mới",
                "autocomplete": "new-password"
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Mật khẩu mới và xác nhận mật khẩu không khớp.")
        return password2

    def clean_new_password1(self):
        password1 = self.cleaned_data.get("new_password1")
        if self.user and password1:
            # Kiểm tra mật khẩu mới không được là mật khẩu mặc định
            if password1 == '12345678':
                raise forms.ValidationError("Mật khẩu mới không được là mật khẩu mặc định (12345678).")
            try:
                validate_password(password1, self.user)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        return password1

    def save(self, commit=True):
        """Lưu mật khẩu mới cho user."""
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user
