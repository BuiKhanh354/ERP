"""Forms for the Accounting module."""
from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceItem, Payment
from projects.models import Project
from clients.models import Client


class InvoiceForm(forms.ModelForm):
    """Form for creating/editing invoices."""

    class Meta:
        model = Invoice
        fields = [
            'project', 'client', 'invoice_number', 'issue_date', 'due_date',
            'tax', 'status', 'notes',
        ]
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select', 'id': 'id_project'}),
            'client': forms.Select(attrs={'class': 'form-select', 'id': 'id_client'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tax': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.all().order_by('name')
        self.fields['client'].queryset = Client.objects.all().order_by('name')


class InvoiceItemForm(forms.ModelForm):
    """Form for invoice line items."""

    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mô tả'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


# Inline formset for invoice items
InvoiceItemFormSet = inlineformset_factory(
    Invoice, InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(forms.ModelForm):
    """Form for recording payments."""

    class Meta:
        model = Payment
        fields = ['invoice', 'amount', 'payment_method', 'payment_date', 'reference_number', 'note']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.exclude(status='paid').order_by('-issue_date')


class ExpenseFilterForm(forms.Form):
    """Form for filtering expenses."""
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(), required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='-- Tất cả dự án --'
    )
    category = forms.CharField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
