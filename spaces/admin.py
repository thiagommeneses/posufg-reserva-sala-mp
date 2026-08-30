"""Admin configuration for the spaces app."""

from django.contrib import admin

from .models import Attribute, Space, SpaceAttribute


class SpaceAttributeInline(admin.TabularInline):
    """Inline admin for space attributes."""

    model = SpaceAttribute
    extra = 1


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    """Admin interface for Space model."""

    list_display = ["name", "capacity", "location", "is_active", "created_at"]
    list_filter = ["is_active", "location"]
    search_fields = ["name", "description", "location"]
    inlines = [SpaceAttributeInline]


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    """Admin interface for Attribute model."""

    list_display = ["name", "category", "is_featured", "sort_order"]
    list_filter = ["is_featured", "category"]
    list_editable = ["is_featured", "sort_order"]
    search_fields = ["name", "category"]


@admin.register(SpaceAttribute)
class SpaceAttributeAdmin(admin.ModelAdmin):
    """Admin interface for SpaceAttribute model."""

    list_display = ["space", "attribute"]
    list_filter = ["attribute"]
    search_fields = ["space__name", "attribute__name"]
