from django import forms
from .models import PerformanceMetric, PerformanceScore


class PerformanceMetricForm(forms.ModelForm):
    class Meta:
        model = PerformanceMetric
        fields = ['metric_type', 'employee', 'project', 'value',
                  'period_start', 'period_end', 'notes']
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }


class PerformanceScoreForm(forms.ModelForm):
    class Meta:
        model = PerformanceScore
        fields = ['employee', 'project', 'overall_score', 'efficiency_score',
                  'quality_score', 'productivity_score', 'period_start', 'period_end', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'overall_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00 - 100.00'
            }),
            'efficiency_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00 - 100.00'
            }),
            'quality_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00 - 100.00'
            }),
            'productivity_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00 - 100.00'
            }),
            'period_start': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'period_end': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ghi chú về đánh giá hiệu suất...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Làm cho project field không bắt buộc
        self.fields['project'].required = False
        self.fields['project'].empty_label = '-- Không chọn dự án --'
