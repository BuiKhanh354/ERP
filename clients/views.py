from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Client, Contact, ClientInteraction
from .serializers import ClientSerializer, ContactSerializer, ClientInteractionSerializer


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]


class ClientInteractionViewSet(viewsets.ModelViewSet):
    queryset = ClientInteraction.objects.all()
    serializer_class = ClientInteractionSerializer
    permission_classes = [IsAuthenticated]

