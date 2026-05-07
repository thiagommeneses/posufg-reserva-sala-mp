"""Admin configuration for the reservations app."""

from django.contrib import admin

from reservations.models import MaintenanceBlock, Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Admin interface for reservations."""

    list_display = [
        "space",
        "user",
        "start_time",
        "end_time",
        "status",
        "created_at",
    ]
    list_filter = ["status", "space", "created_at"]
    search_fields = ["space__name", "user__username"]
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
