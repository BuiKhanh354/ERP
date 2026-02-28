from django import forms
from .models import PayrollSchedule


class PayrollScheduleForm(forms.ModelForm):
    """Form cài đặt lịch phát lương."""
    
    class Meta:
        model = PayrollSchedule
        fields = ['payment_day', 'notes']
        widgets = {
            'payment_day': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ghi chú về lịch phát lương (tùy chọn)'
            }),
        }
        labels = {
            'payment_day': 'Ngày phát lương',
            'notes': 'Ghi chú',
        }
        help_texts = {
            'payment_day': 'Chọn ngày phát lương trong tháng (1-28)',
        }
