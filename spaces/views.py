"""Views for the spaces app."""

import django_filters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from reservations.services import get_availability_for_date

from .models import Attribute, Space
from .serializers import SpaceSerializer


class SpaceFilterSet(django_filters.FilterSet):
    """Filter set for searching spaces by attributes and capacity."""

    min_capacity = django_filters.NumberFilter(field_name="capacity", lookup_expr="gte")
    max_capacity = django_filters.NumberFilter(field_name="capacity", lookup_expr="lte")
    attributes = django_filters.CharFilter(method="filter_attributes")
    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")

    class Meta:
        """Meta options for SpaceFilterSet."""

        model = Space
        fields = ["is_active", "location"]

    def filter_attributes(self, queryset, _name, value):
        """Filter spaces that have all specified attributes."""
        if not value:
            return queryset
        attr_names = [v.strip() for v in value.split(",") if v.strip()]
        for attr_name in attr_names:
            queryset = queryset.filter(space_attributes__attribute__name=attr_name)
        return queryset.distinct()


class SpaceViewSet(viewsets.ModelViewSet):
    """ViewSet for listing, retrieving, creating and updating spaces."""

    queryset = Space.objects.prefetch_related("space_attributes__attribute").all()
    serializer_class = SpaceSerializer
    filterset_class = SpaceFilterSet

    def get_permissions(self):
        """Restrict write operations to admin users."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"], url_path="availability")
    def availability(self, request, pk=None):
        """Return occupied and free time slots for a space on a given date."""
        space = self.get_object()
        date_str = request.query_params.get("date")

        if not date_str:
            raise ValidationError({"date": "This parameter is required."})

        try:
            from datetime import datetime as _dt

            date = _dt.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValidationError({"date": "Invalid date format. Use YYYY-MM-DD."}) from exc

        data = get_availability_for_date(space, date)
        return Response(data)


class SpaceListView(LoginRequiredMixin, ListView):
    """List view for spaces with filtering capabilities."""

    model = Space
    template_name = "spaces/space_list.html"
    context_object_name = "spaces"

    def get_queryset(self):
        """Filter spaces based on query parameters."""
        queryset = Space.objects.filter(is_active=True).prefetch_related(
            "space_attributes__attribute"
        )

        # Filter by minimum capacity
        min_capacity = self.request.GET.get("min_capacity")
        if min_capacity:
            try:
                queryset = queryset.filter(capacity__gte=int(min_capacity))
            except ValueError:
                pass

        # Filter by attributes (comma-separated list)
        attributes = self.request.GET.get("attributes")
        if attributes:
            attr_names = [a.strip() for a in attributes.split(",") if a.strip()]
            for attr_name in attr_names:
                queryset = queryset.filter(space_attributes__attribute__name=attr_name)
            queryset = queryset.distinct()

        # Filter by location (case-insensitive)
        location = self.request.GET.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        """Add filter options and selected filters to context."""
        context = super().get_context_data(**kwargs)
        context["attributes"] = Attribute.objects.order_by("name")
        context["selected_attributes"] = self.request.GET.get("attributes", "")
        context["min_capacity"] = self.request.GET.get("min_capacity", "")
        context["location"] = self.request.GET.get("location", "")
        context["is_htmx"] = self.request.headers.get("HX-Request") == "true"
        return context

    def get_template_names(self):
        """Return partial template for HTMX requests."""
        if self.request.headers.get("HX-Request") == "true":
            return ["spaces/_space_list_results.html"]
        return [self.template_name]
