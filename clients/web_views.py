"""Web views for Client Management."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .models import Client, Contact, ClientInteraction
from .forms import ClientForm, ContactForm, ClientInteractionForm
from projects.models import Project
from core.mixins import ManagerRequiredMixin


class ClientListView(LoginRequiredMixin, ListView):
    """Danh sách khách hàng."""
    model = Client
    template_name = 'clients/list.html'
    context_object_name = 'clients'
    paginate_by = 20

    def get_queryset(self):
        # Quản lý xem tất cả, nhân viên chỉ xem của mình
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            queryset = Client.objects.all().annotate(
                project_count=Count('projects'),
                contact_count=Count('contacts')
            )
        else:
            queryset = Client.objects.filter(created_by=user).annotate(
                project_count=Count('projects', filter=Q(projects__created_by=user)),
                contact_count=Count('contacts')
            )
        queryset = queryset.order_by('-created_at')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(industry__icontains=search)
            )

        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        client_type_filter = self.request.GET.get('client_type')
        if client_type_filter:
            queryset = queryset.filter(client_type=client_type_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['client_type_filter'] = self.request.GET.get('client_type', '')
        
        # Stats - quản lý xem tất cả, nhân viên chỉ của mình
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            user_clients = Client.objects.all()
        else:
            user_clients = Client.objects.filter(created_by=user)
        context['total_clients'] = user_clients.count()
        context['active_clients'] = user_clients.filter(status='active').count()
        context['prospect_clients'] = user_clients.filter(status='prospect').count()
        
        return context


class ClientDetailView(LoginRequiredMixin, DetailView):
    """Chi tiết khách hàng."""
    model = Client
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        """Quản lý xem tất cả, nhân viên chỉ xem của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Client.objects.all()
        return Client.objects.filter(created_by=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.get_object()
        
        context['contacts'] = client.contacts.filter(created_by=self.request.user)
        context['interactions'] = client.interactions.filter(created_by=self.request.user).select_related('contact').order_by('-date')[:10]
        context['projects'] = Project.objects.filter(client=client, created_by=self.request.user)
        
        return context


class ClientCreateView(ManagerRequiredMixin, CreateView):
    """Tạo khách hàng mới - chỉ quản lý mới có quyền."""
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Đã tạo khách hàng "{form.instance.name}" thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Tạo khách hàng mới'
        context['submit_text'] = 'Tạo khách hàng'
        return context


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    """Cập nhật khách hàng."""
    model = Client
    form_class = ClientForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        """Quản lý có thể sửa tất cả, nhân viên chỉ sửa của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Client.objects.all()
        return Client.objects.filter(created_by=user)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Đã cập nhật khách hàng "{form.instance.name}" thành công.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Chỉnh sửa: {self.get_object().name}'
        context['submit_text'] = 'Cập nhật'
        return context


class ClientDeleteView(LoginRequiredMixin, DeleteView):
    """Xóa khách hàng."""
    model = Client
    template_name = 'clients/confirm_delete.html'
    success_url = reverse_lazy('clients:list')

    def get_queryset(self):
        """Quản lý có thể xóa tất cả, nhân viên chỉ xóa của mình."""
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.is_manager():
            return Client.objects.all()
        return Client.objects.filter(created_by=user)

    def delete(self, request, *args, **kwargs):
        client = self.get_object()
        messages.success(request, f'Đã xóa khách hàng "{client.name}".')
        return super().delete(request, *args, **kwargs)


class ContactCreateView(LoginRequiredMixin, CreateView):
    """Tạo liên hệ mới."""
    model = Contact
    form_class = ContactForm
    template_name = 'clients/contact_form.html'

    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.client.pk})

    def form_valid(self, form):
        client_id = self.kwargs.get('client_id')
        if client_id:
            # Chỉ cho phép thêm contact cho client của user hiện tại
            form.instance.client = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Đã thêm liên hệ "{form.instance.full_name}" thành công.')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.kwargs.get('client_id')
        if client_id:
            initial['client'] = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_id = self.kwargs.get('client_id')
        if client_id:
            context['client'] = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        context['page_title'] = 'Thêm liên hệ mới'
        context['submit_text'] = 'Thêm liên hệ'
        return context


class InteractionCreateView(LoginRequiredMixin, CreateView):
    """Tạo tương tác mới."""
    model = ClientInteraction
    form_class = ClientInteractionForm
    template_name = 'clients/interaction_form.html'

    def get_success_url(self):
        return reverse_lazy('clients:detail', kwargs={'pk': self.object.client.pk})

    def form_valid(self, form):
        client_id = self.kwargs.get('client_id')
        if client_id:
            # Chỉ cho phép thêm interaction cho client của user hiện tại
            form.instance.client = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Đã thêm tương tác "{form.instance.subject}" thành công.')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.kwargs.get('client_id')
        if client_id:
            initial['client'] = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_id = self.kwargs.get('client_id')
        if client_id:
            context['client'] = get_object_or_404(Client, pk=client_id, created_by=self.request.user)
        context['page_title'] = 'Thêm tương tác mới'
        context['submit_text'] = 'Thêm tương tác'
        return context
