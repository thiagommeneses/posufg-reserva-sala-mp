"""Views for the spaces app."""

import django_filters
from rest_framework import permissions, viewsets

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
