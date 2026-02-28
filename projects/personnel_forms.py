"""Forms for personnel recommendation."""
from django import forms
from .models import PersonnelRecommendation


class PersonnelRecommendationForm(forms.Form):
    """Form để chọn mục tiêu tối ưu hóa cho đề xuất nhân sự."""
    
    OPTIMIZATION_GOAL_CHOICES = [
        ('performance', 'Tối ưu hiệu suất'),
        ('cost', 'Tối ưu chi phí'),
        ('balanced', 'Cân bằng'),
    ]
    
    optimization_goal = forms.ChoiceField(
        choices=OPTIMIZATION_GOAL_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        label='Mục tiêu tối ưu hóa',
        initial='balanced',
        help_text='Chọn mục tiêu cho việc đề xuất nhân sự'
    )
    
    use_ai = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Sử dụng AI để đề xuất',
        help_text='Bỏ chọn để chỉ dùng thuật toán rule-based'
    )
