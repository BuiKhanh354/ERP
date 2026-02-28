from django.contrib import admin
from .models import Client, Contact, ClientInteraction


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'client_type', 'status', 'email', 'phone', 'industry']
    list_filter = ['client_type', 'status', 'created_at']
    search_fields = ['name', 'email', 'industry']
    date_hierarchy = 'created_at'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'client', 'email', 'phone', 'position', 'is_primary']
    list_filter = ['is_primary', 'client']
    search_fields = ['first_name', 'last_name', 'email']


@admin.register(ClientInteraction)
class ClientInteractionAdmin(admin.ModelAdmin):
    list_display = ['client', 'contact', 'interaction_type', 'date', 'subject', 'follow_up_required']
    list_filter = ['interaction_type', 'follow_up_required', 'date']
    search_fields = ['subject', 'description', 'client__name']
    date_hierarchy = 'date'

