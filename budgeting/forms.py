from django import forms
from django.utils import timezone
from .models import BudgetCategory, Budget, Expense


class BudgetCategoryForm(forms.ModelForm):
    class Meta:
        model = BudgetCategory
        fields = ['name', 'description', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tên danh mục'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mô tả danh mục'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'name': 'Tên danh mục',
            'description': 'Mô tả',
            'parent': 'Danh mục cha',
        }


class BudgetForm(forms.ModelForm):
    EXPENSE_TYPE_CHOICES = [
        ('labor', 'Nhân công'),
        ('material', 'Vật liệu'),
        ('equipment', 'Thiết bị'),
        ('travel', 'Đi lại'),
        ('other', 'Khác'),
    ]

    class Meta:
        model = Budget
        fields = ['project', 'category', 'allocated_amount', 'fiscal_year', 'notes']
        widgets = {
            'project': forms.Select(attrs={
                'class': 'form-select'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'allocated_amount': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': '0',
                'style': 'padding-right: 60px;'
            }),
            'fiscal_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2000',
                'max': '2100'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ghi chú'
            }),
        }
        labels = {
            'project': 'Dự án',
            'category': 'Danh mục',
            'allocated_amount': 'Số tiền phân bổ',
            'fiscal_year': 'Năm tài chính',
            'notes': 'Ghi chú',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['fiscal_year'].initial = timezone.now().year


class ExpenseForm(forms.ModelForm):
    EXPENSE_TYPE_CHOICES = [
        ('labor', 'Nhân công'),
        ('material', 'Vật liệu'),
        ('equipment', 'Thiết bị'),
        ('travel', 'Đi lại'),
        ('other', 'Khác'),
    ]

    expense_type = forms.ChoiceField(
        choices=EXPENSE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Loại chi phí'
    )

    class Meta:
        model = Expense
        fields = ['project', 'budget', 'category', 'expense_type', 'amount',
                  'description', 'expense_date', 'vendor', 'invoice_number']
        widgets = {
            'project': forms.Select(attrs={
                'class': 'form-select'
            }),
            'budget': forms.Select(attrs={
                'class': 'form-select'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'amount': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': '0',
                'style': 'padding-right: 60px;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mô tả chi phí'
            }),
            'expense_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'vendor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhà cung cấp'
            }),
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Số hóa đơn'
            }),
        }
        labels = {
            'project': 'Dự án',
            'budget': 'Ngân sách',
            'category': 'Danh mục',
            'amount': 'Số tiền',
            'description': 'Mô tả',
            'expense_date': 'Ngày chi phí',
            'vendor': 'Nhà cung cấp',
            'invoice_number': 'Số hóa đơn',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['expense_date'].initial = timezone.now().date()