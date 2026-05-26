"""Views for the reservations app."""

import datetime

import django_filters
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from reservations.models import MaintenanceBlock, Reservation
from reservations.serializers import MaintenanceBlockSerializer, ReservationSerializer
from reservations.services import (
    OwnershipError,
    cancel_reservation,
    check_in_reservation,
    reschedule_reservation,
)
from spaces.models import Space


class RescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a reservation."""

    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    class Meta:
        """Meta options for RescheduleSerializer."""

        fields = ["start_time", "end_time"]


class ReservationFilterSet(django_filters.FilterSet):
    """Filter set for user reservations."""

    start_time__gte = django_filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    start_time__lte = django_filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")

    class Meta:
        """Meta options for ReservationFilterSet."""

        model = Reservation
        fields = ["status", "space"]


class MaintenanceBlockViewSet(viewsets.ModelViewSet):
    """ViewSet for creating, listing and deleting maintenance blocks (admin only)."""

    queryset = MaintenanceBlock.objects.all()
    serializer_class = MaintenanceBlockSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        """Automatically set created_by from the request user."""
        serializer.save(created_by=self.request.user)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for listing and creating reservations."""

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ReservationFilterSet

    def get_queryset(self):
        """Users see only their own reservations, ordered by start_time descending."""
        return Reservation.objects.filter(user=self.request.user).order_by("-start_time")

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


class OccupancyView(APIView):
    """Admin-only view for occupancy overview of all spaces on a given date."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """Return all spaces with their reservations and maintenance blocks for a date.

        Query Parameters:
            date: Date in YYYY-MM-DD format (required)

        Returns:
            Response with list of spaces including reservations and maintenance blocks.
        """
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Date parameter is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_start = datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=datetime.UTC,
        )
        date_end = date_start + datetime.timedelta(days=1)

        spaces = Space.objects.all().order_by("name")
        occupancy_data = []

        for space in spaces:
            reservations = Reservation.objects.filter(
                space=space,
                start_time__lt=date_end,
                end_time__gt=date_start,
            ).select_related("user")

            reservation_list = [
                {
                    "id": r.id,
                    "user": r.user.username,
                    "start_time": r.start_time.isoformat().replace("+00:00", "Z"),
                    "end_time": r.end_time.isoformat().replace("+00:00", "Z"),
                    "status": r.status,
                }
                for r in reservations
            ]

            maintenance_blocks = MaintenanceBlock.objects.filter(
                space=space,
                start_time__lt=date_end,
                end_time__gt=date_start,
            )

            block_list = [
                {
                    "id": b.id,
                    "start_time": b.start_time.isoformat().replace("+00:00", "Z"),
                    "end_time": b.end_time.isoformat().replace("+00:00", "Z"),
                    "reason": b.reason,
                }
                for b in maintenance_blocks
            ]

            occupancy_data.append(
                {
                    "id": space.id,
                    "name": space.name,
                    "capacity": space.capacity,
                    "location": space.location,
                    "is_active": space.is_active,
                    "reservations": reservation_list,
                    "maintenance_blocks": block_list,
                }
            )

        return Response(
            {
                "date": date_str,
                "spaces": occupancy_data,
            }
        )
