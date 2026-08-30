"""Admin configuration for the reservations app."""

from django.contrib import admin

from reservations.models import MaintenanceBlock, Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Admin interface for reservations."""

    list_display = [
        "space",
        "title",
        "user",
        "start_time",
        "end_time",
        "attendee_count",
        "status",
    ]
    list_filter = ["status", "space", "created_at"]
    search_fields = ["space__name", "user__username", "title"]
    ordering = ["-start_time"]


@admin.register(MaintenanceBlock)
class MaintenanceBlockAdmin(admin.ModelAdmin):
    """Admin interface for maintenance blocks."""

    list_display = [
        "space",
        "reason",
        "start_time",
        "end_time",
        "created_by",
    ]
    list_filter = ["space", "created_at"]
    search_fields = ["space__name", "reason"]
    ordering = ["-start_time"]
