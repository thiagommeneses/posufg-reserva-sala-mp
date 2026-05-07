"""Views for the spaces app."""

import django_filters
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from reservations.services import get_availability_for_date

from .models import Space
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
