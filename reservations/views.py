"""Views for the reservations app."""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from reservations.models import Reservation
from reservations.serializers import ReservationSerializer
from reservations.services import (
    OwnershipError,
    cancel_reservation,
    check_in_reservation,
    reschedule_reservation,
)


class RescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a reservation."""

    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    class Meta:
        """Meta options for RescheduleSerializer."""

        fields = ["start_time", "end_time"]


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

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        """Cancel a reservation."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            cancel_reservation(reservation, request.user)
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """Check in to a reservation."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            check_in_reservation(reservation, request.user)
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = self.get_serializer(reservation)
        return Response(response_serializer.data)

    @action(detail=True, methods=["patch"])
    def reschedule(self, request, pk=None):
        """Reschedule a reservation to a new time slot."""
        reservation = get_object_or_404(Reservation, pk=pk)
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reschedule_reservation(
                reservation,
                request.user,
                serializer.validated_data["start_time"],
                serializer.validated_data["end_time"],
            )
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = self.get_serializer(reservation)
        return Response(response_serializer.data)
