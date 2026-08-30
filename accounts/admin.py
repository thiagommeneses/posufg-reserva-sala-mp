"""Django admin configuration for accounts app."""

from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for user profiles."""

    list_display = ["user", "full_name", "department", "updated_at"]
    search_fields = ["user__username", "full_name", "department"]
