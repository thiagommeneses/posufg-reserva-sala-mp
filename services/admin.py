"""Django admin configuration for the services app."""

from django.contrib import admin

from services.models import ReservationServiceRequest, ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    """Admin interface for the service catalog."""

    list_display = [
        "name",
        "category",
        "min_lead_time_hours",
        "requires_notes",
        "is_active",
        "sort_order",
    ]
    list_filter = ["is_active", "category", "requires_notes"]
    search_fields = ["name", "slug", "description"]
    filter_horizontal = ["spaces"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ReservationServiceRequest)
class ReservationServiceRequestAdmin(admin.ModelAdmin):
    """Admin interface for the service request queue."""

    list_display = ["service_type", "reservation", "status", "processed_by", "processed_at"]
    list_filter = ["status", "service_type"]
    search_fields = ["reservation__space__name", "reservation__user__username", "notes"]
    autocomplete_fields = ["reservation"]
