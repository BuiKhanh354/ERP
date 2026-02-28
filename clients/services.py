"""Client business logic services."""
from django.db.models import Count, Sum
from django.utils import timezone
from .models import Client, ClientInteraction
from projects.models import Project


class ClientService:
    """Service class for client-related operations."""

    @staticmethod
    def get_client_summary(client_id):
        """Get comprehensive summary for a client."""
        client = Client.objects.get(id=client_id)
        projects = Project.objects.filter(client=client)
        interactions = ClientInteraction.objects.filter(client=client)
        
        total_projects = projects.count()
        active_projects = projects.filter(status='active').count()
        total_value = projects.aggregate(total=Sum('estimated_budget'))['total'] or 0
        
        return {
            'client': client,
            'total_projects': total_projects,
            'active_projects': active_projects,
            'total_value': total_value,
            'recent_interactions': interactions[:5],
        }

    @staticmethod
    def get_top_clients_by_value(limit=10):
        """Get top clients by project value."""
        clients = Client.objects.annotate(
            total_value=Sum('projects__estimated_budget')
        ).filter(total_value__gt=0).order_by('-total_value')[:limit]
        
        return clients

