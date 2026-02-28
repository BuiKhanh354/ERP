from django import forms
from .models import Client, Contact, ClientInteraction


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'client_type', 'status', 'email', 'phone',
                  'address', 'website', 'industry', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên khách hàng'}),
            'client_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Địa chỉ'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
            'industry': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ngành nghề'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ghi chú'}),
        }
        labels = {
            'name': 'Tên khách hàng',
            'client_type': 'Loại khách hàng',
            'status': 'Trạng thái',
            'email': 'Email',
            'phone': 'Số điện thoại',
            'address': 'Địa chỉ',
            'website': 'Website',
            'industry': 'Ngành nghề',
            'notes': 'Ghi chú',
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['client', 'first_name', 'last_name', 'email', 'phone',
                  'position', 'is_primary', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chức vụ'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ghi chú'}),
        }
        labels = {
            'client': 'Khách hàng',
            'first_name': 'Tên',
            'last_name': 'Họ',
            'email': 'Email',
            'phone': 'Số điện thoại',
            'position': 'Chức vụ',
            'is_primary': 'Liên hệ chính',
            'notes': 'Ghi chú',
        }


class ClientInteractionForm(forms.ModelForm):
    class Meta:
        model = ClientInteraction
        fields = ['client', 'contact', 'interaction_type', 'date', 'subject',
                  'description', 'follow_up_required', 'follow_up_date']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'interaction_type': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiêu đề'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Mô tả'}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'client': 'Khách hàng',
            'contact': 'Liên hệ',
            'interaction_type': 'Loại tương tác',
            'date': 'Ngày giờ',
            'subject': 'Tiêu đề',
            'description': 'Mô tả',
            'follow_up_required': 'Cần theo dõi',
            'follow_up_date': 'Ngày theo dõi',
        }

