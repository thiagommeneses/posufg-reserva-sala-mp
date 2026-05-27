"""Views for the admin dashboard app."""

import datetime

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from reservations.services import admin_cancel_reservation
from spaces.models import Space

from .forms import SpaceForm


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be staff."""

    def test_func(self):
        """Return True if the user is staff."""
        return self.request.user.is_staff


class AdminDashboardView(StaffRequiredMixin, View):
    """Admin dashboard view showing real-time occupancy overview."""

    template_name = "admin_dashboard/index.html"

    def get(self, request):
        """Render the admin dashboard with occupancy metrics and space cards."""
        now = datetime.datetime.now(datetime.UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)

        total_spaces = Space.objects.count()

        # Occupied now: confirmed or checked_in reservations overlapping current time
        occupied_reservation_space_ids = set(
            Reservation.objects.filter(
                space__isnull=False,
                status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
                start_time__lte=now,
                end_time__gt=now,
            ).values_list("space_id", flat=True)
        )

        # Maintenance now: maintenance blocks overlapping current time
        maintenance_space_ids = set(
            MaintenanceBlock.objects.filter(
                space__isnull=False,
                start_time__lte=now,
                end_time__gt=now,
            ).values_list("space_id", flat=True)
        )

        occupied_now = len(occupied_reservation_space_ids)
        maintenance_now = len(maintenance_space_ids)
        available_now = total_spaces - occupied_now - maintenance_now

        # No-shows today
        no_shows_today = Reservation.objects.filter(
            status=ReservationStatus.NO_SHOW,
            start_time__gte=today_start,
            start_time__lt=today_end,
        ).count()

        # Space cards data
        spaces = Space.objects.all().order_by("name")
        space_cards = []
        for space in spaces:
            if space.id in maintenance_space_ids:
                status = "maintenance"
                status_label = "Manutenção"
                status_class = "badge-warning"
            elif space.id in occupied_reservation_space_ids:
                status = "occupied"
                status_label = "Ocupado"
                status_class = "badge-error"
            else:
                status = "free"
                status_label = "Livre"
                status_class = "badge-success"

            space_cards.append(
                {
                    "id": space.id,
                    "name": space.name,
                    "capacity": space.capacity,
                    "location": space.location,
                    "is_active": space.is_active,
                    "status": status,
                    "status_label": status_label,
                    "status_class": status_class,
                }
            )

        context = {
            "total_spaces": total_spaces,
            "occupied_now": occupied_now,
            "available_now": available_now,
            "maintenance_now": maintenance_now,
            "no_shows_today": no_shows_today,
            "space_cards": space_cards,
        }

        # HTMX partial refresh
        if request.headers.get("HX-Request") == "true":
            return render(request, "admin_dashboard/_occupancy_grid.html", context)

        return render(request, self.template_name, context)


class AdminSpaceListView(StaffRequiredMixin, ListView):
    """List view for admin space management."""

    model = Space
    template_name = "admin_dashboard/space_list.html"
    context_object_name = "spaces"
    queryset = Space.objects.prefetch_related("space_attributes__attribute").order_by("name")


class AdminSpaceCreateView(StaffRequiredMixin, CreateView):
    """Create view for spaces (admin only)."""

    model = Space
    form_class = SpaceForm
    template_name = "admin_dashboard/space_form.html"
    success_url = reverse_lazy("admin_dashboard:space_list")


class AdminSpaceUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for spaces (admin only)."""

    model = Space
    form_class = SpaceForm
    template_name = "admin_dashboard/space_form.html"
    success_url = reverse_lazy("admin_dashboard:space_list")


class AdminSpaceToggleView(StaffRequiredMixin, View):
    """Toggle the is_active status of a space inline (admin only)."""

    def patch(self, request, pk):
        """Toggle is_active and return the updated badge HTML."""
        space = get_object_or_404(Space, pk=pk)
        space.is_active = not space.is_active
        space.save(update_fields=["is_active"])
        if space.is_active:
            badge = '<span class="badge badge-success">Ativo</span>'
        else:
            badge = '<span class="badge badge-ghost">Inativo</span>'
        return HttpResponse(badge)


class AdminReservationListView(StaffRequiredMixin, ListView):
    """List view for admin reservation management with filtering."""

    model = Reservation
    template_name = "admin_dashboard/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 25

    def get_queryset(self):
        """Return filtered queryset based on query parameters."""
        queryset = Reservation.objects.select_related("space", "user").order_by("-start_time")

        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        space_filter = self.request.GET.get("space")
        if space_filter:
            queryset = queryset.filter(space_id=space_filter)

        start_date = self.request.GET.get("start_date")
        if start_date:
            try:
                parsed = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
                dt_start = datetime.datetime.combine(parsed, datetime.time.min).replace(
                    tzinfo=datetime.UTC,
                )
                queryset = queryset.filter(start_time__gte=dt_start)
            except ValueError:
                pass

        end_date = self.request.GET.get("end_date")
        if end_date:
            try:
                parsed = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
                dt_end = datetime.datetime.combine(parsed, datetime.time.max).replace(
                    tzinfo=datetime.UTC,
                )
                queryset = queryset.filter(start_time__lte=dt_end)
            except ValueError:
                pass

        user_search = self.request.GET.get("user_search")
        if user_search:
            queryset = queryset.filter(user__username__icontains=user_search)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and current filter values to context."""
        context = super().get_context_data(**kwargs)
        context["spaces"] = Space.objects.order_by("name")
        context["status_choices"] = ReservationStatus.choices
        context["current_filters"] = {
            "status": self.request.GET.get("status", ""),
            "space": self.request.GET.get("space", ""),
            "start_date": self.request.GET.get("start_date", ""),
            "end_date": self.request.GET.get("end_date", ""),
            "user_search": self.request.GET.get("user_search", ""),
        }
        return context

    def render_to_response(self, context, **response_kwargs):
        """Return partial template for HTMX filter requests."""
        if self.request.headers.get("HX-Request") == "true":
            return render(
                self.request,
                "admin_dashboard/_reservation_table.html",
                context,
            )
        return super().render_to_response(context, **response_kwargs)


class AdminReservationCancelView(StaffRequiredMixin, View):
    """Cancel any reservation (admin only)."""

    def post(self, request, pk):
        """Cancel the reservation and return the updated row HTML."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            admin_cancel_reservation(reservation)
        except ValidationError as exc:
            return HttpResponse(
                f'<span class="text-error text-sm">{exc.message}</span>',
                status=400,
            )

        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "admin_dashboard/_reservation_row.html",
                {"reservation": reservation},
            )

        return render(request, "admin_dashboard/reservation_list.html")
