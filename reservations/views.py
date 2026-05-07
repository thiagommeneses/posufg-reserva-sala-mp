"""Views for the reservations app."""

from rest_framework import permissions, viewsets

from reservations.models import Reservation
from reservations.serializers import ReservationSerializer


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for listing and creating reservations."""

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Users see only their own reservations."""
        return Reservation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Automatically set user and confirmed status on creation."""
        serializer.save(user=self.request.user)
