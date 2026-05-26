"""Views for the reservations app."""

import datetime

import django_filters
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from reservations.serializers import MaintenanceBlockSerializer, ReservationSerializer
from reservations.services import (
    CHECK_IN_WINDOW_MINUTES,
    OwnershipError,
    cancel_reservation,
    check_in_reservation,
    create_reservation,
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


class ReservationListView(LoginRequiredMixin, View):
    """List view for the authenticated user's reservations."""

    template_name = "reservations/reservation_list.html"

    def get(self, request):
        """Render the user's reservations with tab filtering."""
        reservations = Reservation.objects.filter(user=request.user).order_by("-start_time")

        now = datetime.datetime.now(datetime.UTC)

        # Calculate counts for tabs
        active_count = reservations.filter(
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
            end_time__gte=now,
        ).count()

        past_count = reservations.filter(
            models.Q(end_time__lt=now)
            | models.Q(status__in=[ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW]),
        ).count()

        cancelled_count = reservations.filter(
            status=ReservationStatus.CANCELLED,
        ).count()

        # Determine active tab
        active_tab = request.GET.get("tab", "active")
        if active_tab not in ["active", "past", "cancelled"]:
            active_tab = "active"

        # Filter reservations based on tab
        if active_tab == "active":
            filtered_reservations = reservations.filter(
                status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
                end_time__gte=now,
            )
        elif active_tab == "past":
            filtered_reservations = reservations.filter(
                models.Q(end_time__lt=now)
                | models.Q(
                    status__in=[ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW],
                ),
            )
        else:  # cancelled
            filtered_reservations = reservations.filter(
                status=ReservationStatus.CANCELLED,
            )

        return render(
            request,
            self.template_name,
            {
                "reservations": reservations,
                "filtered_reservations": filtered_reservations,
                "active_tab": active_tab,
                "active_count": active_count,
                "past_count": past_count,
                "cancelled_count": cancelled_count,
            },
        )


class ReservationDetailView(LoginRequiredMixin, View):
    """Detail view for a single reservation."""

    template_name = "reservations/reservation_detail.html"

    def get(self, request, pk):
        """Render the reservation detail page with action buttons context."""
        reservation = get_object_or_404(
            Reservation,
            pk=pk,
            user=request.user,
        )

        now = datetime.datetime.now(datetime.UTC)

        # Determine which actions are available
        can_cancel = reservation.status in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }

        can_check_in = (
            reservation.status == ReservationStatus.CONFIRMED
            and reservation.start_time - datetime.timedelta(minutes=CHECK_IN_WINDOW_MINUTES)
            <= now
            <= reservation.end_time
        )

        can_reschedule = reservation.status in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }

        return render(
            request,
            self.template_name,
            {
                "reservation": reservation,
                "can_cancel": can_cancel,
                "can_check_in": can_check_in,
                "can_reschedule": can_reschedule,
            },
        )


class ReservationCreateView(LoginRequiredMixin, View):
    """View for creating a reservation via web interface."""

    template_name = "reservations/reservation_form.html"

    def get(self, request):
        """Render the reservation creation form.

        Pre-fills space and start time from query parameters if provided.
        """
        space_id = request.GET.get("space")
        space = get_object_or_404(Space, pk=space_id, is_active=True) if space_id else None

        start_iso = request.GET.get("start", "")
        prefill_date = ""
        prefill_start_time = ""
        prefill_end_time = ""

        if start_iso:
            try:
                dt = datetime.datetime.fromisoformat(
                    start_iso.replace("Z", "+00:00"),
                )
                prefill_date = dt.strftime("%Y-%m-%d")
                prefill_start_time = dt.strftime("%H:%M")
                end_dt = dt + datetime.timedelta(hours=1)
                prefill_end_time = end_dt.strftime("%H:%M")
            except ValueError:
                pass

        context = {
            "space": space,
            "prefill_date": prefill_date,
            "prefill_start_time": prefill_start_time,
            "prefill_end_time": prefill_end_time,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Process the reservation creation form."""
        space_id = request.POST.get("space")
        space = get_object_or_404(Space, pk=space_id, is_active=True)

        date_str = request.POST.get("date", "").strip()
        start_time_str = request.POST.get("start_time", "").strip()
        end_time_str = request.POST.get("end_time", "").strip()

        try:
            start_time = self._parse_datetime(date_str, start_time_str)
            end_time = self._parse_datetime(date_str, end_time_str)
        except ValueError:
            context = {
                "space": space,
                "error": "Formato de data ou hora inválido.",
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

        try:
            reservation = create_reservation(request.user, space, start_time, end_time)
            messages.success(request, "Reserva criada com sucesso!")
            return redirect("reservation_detail", pk=reservation.pk)
        except ValidationError as exc:
            context = {
                "space": space,
                "error": str(exc),
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> datetime.datetime:
        """Combine date and time strings into a timezone-aware datetime."""
        if not date_str or not time_str:
            raise ValueError("Missing date or time")
        dt = datetime.datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %H:%M",
        )
        return dt.replace(tzinfo=datetime.UTC)


class ReservationCancelView(LoginRequiredMixin, View):
    """View for canceling a reservation via web interface."""

    def post(self, request, pk):
        """Cancel the reservation and redirect with success message."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        try:
            cancel_reservation(reservation, request.user)
            messages.success(request, "Reserva cancelada com sucesso!")
        except OwnershipError:
            messages.error(request, "Você não tem permissão para cancelar esta reserva.")
        except ValidationError as exc:
            messages.error(request, str(exc))

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            return render(
                request,
                "reservations/reservation_detail.html",
                {
                    "reservation": reservation,
                    "can_cancel": False,
                    "can_check_in": False,
                    "can_reschedule": False,
                },
            )

        return redirect("reservation_detail", pk=pk)


class ReservationCheckInView(LoginRequiredMixin, View):
    """View for checking in to a reservation via web interface."""

    def post(self, request, pk):
        """Check in to the reservation and redirect with success message."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        try:
            check_in_reservation(reservation, request.user)
            messages.success(request, "Check-in realizado com sucesso!")
        except OwnershipError:
            messages.error(request, "Você não tem permissão para fazer check-in nesta reserva.")
        except ValidationError as exc:
            messages.error(request, str(exc))

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            return render(
                request,
                "reservations/reservation_detail.html",
                {
                    "reservation": reservation,
                    "can_cancel": reservation.status
                    in {ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN},
                    "can_check_in": False,
                    "can_reschedule": reservation.status
                    in {ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN},
                },
            )

        return redirect("reservation_detail", pk=pk)


class ReservationRescheduleView(LoginRequiredMixin, View):
    """View for rescheduling a reservation via web interface."""

    template_name = "reservations/reservation_reschedule.html"

    def get(self, request, pk):
        """Render the reschedule form."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        # Only allow rescheduling confirmed or checked-in reservations
        if reservation.status not in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }:
            messages.error(request, "Esta reserva não pode ser reagendada.")
            return redirect("reservation_detail", pk=pk)

        context = {
            "reservation": reservation,
            "prefill_date": reservation.start_time.strftime("%Y-%m-%d"),
            "prefill_start_time": reservation.start_time.strftime("%H:%M"),
            "prefill_end_time": reservation.end_time.strftime("%H:%M"),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        """Process the reschedule form."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        date_str = request.POST.get("date", "").strip()
        start_time_str = request.POST.get("start_time", "").strip()
        end_time_str = request.POST.get("end_time", "").strip()

        try:
            start_time = self._parse_datetime(date_str, start_time_str)
            end_time = self._parse_datetime(date_str, end_time_str)
        except ValueError:
            context = {
                "reservation": reservation,
                "error": "Formato de data ou hora inválido.",
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

        try:
            reschedule_reservation(reservation, request.user, start_time, end_time)
            messages.success(request, "Reserva reagendada com sucesso!")
            return redirect("reservation_detail", pk=pk)
        except OwnershipError:
            messages.error(request, "Você não tem permissão para reagendar esta reserva.")
            return redirect("reservation_detail", pk=pk)
        except ValidationError as exc:
            context = {
                "reservation": reservation,
                "error": str(exc),
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> datetime.datetime:
        """Combine date and time strings into a timezone-aware datetime."""
        if not date_str or not time_str:
            raise ValueError("Missing date or time")
        dt = datetime.datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %H:%M",
        )
        return dt.replace(tzinfo=datetime.UTC)
