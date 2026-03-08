"""Serializers for the Accounting module API."""
from rest_framework import serializers
from .models import Invoice, InvoiceItem, Payment


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total']
        read_only_fields = ['total']


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    amount_paid = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'project', 'project_name', 'client', 'client_name',
            'invoice_number', 'issue_date', 'due_date', 'total_amount',
            'tax', 'status', 'notes', 'items', 'amount_paid', 'amount_due',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_number', 'amount', 'payment_method',
            'payment_date', 'reference_number', 'note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
