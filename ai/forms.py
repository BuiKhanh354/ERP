from django import forms
from .models import AIInsight


class AIInsightForm(forms.ModelForm):
    class Meta:
        model = AIInsight
        fields = ['insight_type', 'title', 'summary', 'insights', 'recommendations', 'context_data', 'is_active']

