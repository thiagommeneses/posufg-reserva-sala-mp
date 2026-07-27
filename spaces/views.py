"""Views for the spaces app."""

import datetime

import django_filters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import extract_room_search_filters
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

        ai_query = self.request.GET.get("ai_query", "").strip()
        if ai_query:
            return self._filter_by_ai_query(queryset, ai_query)

        # Filter by capacity bounds
        min_capacity = self.request.GET.get("min_capacity")
        if min_capacity:
            try:
                queryset = queryset.filter(capacity__gte=int(min_capacity))
            except ValueError:
                pass

        max_capacity = self.request.GET.get("max_capacity")
        if max_capacity:
            try:
                queryset = queryset.filter(capacity__lte=int(max_capacity))
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

    def _filter_by_ai_query(self, queryset, ai_query):
        """Interpret a natural-language search via the AI service and filter spaces.

        Stores ``ai_summary`` or ``ai_error`` on the instance for get_context_data.
        """
        try:
            filters = extract_room_search_filters(ai_query)
        except AIServiceError as exc:
            self.ai_error = str(exc)
            return queryset.none()

        self.ai_summary = filters["summary"]
        if filters.get("min_capacity"):
            queryset = queryset.filter(capacity__gte=filters["min_capacity"])
        if filters.get("max_capacity"):
            queryset = queryset.filter(capacity__lte=filters["max_capacity"])
        if filters["location"]:
            queryset = queryset.filter(location__icontains=filters["location"])
        for attribute_name in filters["attributes"]:
            queryset = queryset.filter(space_attributes__attribute__name__icontains=attribute_name)

        return queryset.distinct().order_by("name")

    def get_context_data(self, **kwargs):
        """Add filter options and selected filters to context."""
        context = super().get_context_data(**kwargs)
        context["attributes"] = Attribute.objects.order_by("name")
        context["selected_attributes"] = self.request.GET.get("attributes", "")
        context["min_capacity"] = self.request.GET.get("min_capacity", "")
        context["max_capacity"] = self.request.GET.get("max_capacity", "")
        context["location"] = self.request.GET.get("location", "")
        context["ai_query"] = self.request.GET.get("ai_query", "")
        context["ai_summary"] = getattr(self, "ai_summary", "")
        context["ai_error"] = getattr(self, "ai_error", "")
        context["is_htmx"] = self.request.headers.get("HX-Request") == "true"
        return context

    def get_template_names(self):
        """Return partial template for HTMX requests."""
        if self.request.headers.get("HX-Request") == "true":
            return ["spaces/_space_list_results.html"]
        return [self.template_name]


class SpaceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a space showing info and availability calendar."""

    model = Space
    template_name = "spaces/space_detail.html"
    context_object_name = "space"

    def get_queryset(self):
        """Prefetch related attributes for the space."""
        return Space.objects.filter(is_active=True).prefetch_related("space_attributes__attribute")

    def get_context_data(self, **kwargs):
        """Add availability data and selected date to context."""
        context = super().get_context_data(**kwargs)
        space = self.get_object()

        # Get date from query param or default to today
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                from datetime import datetime as _dt

                selected_date = _dt.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.date.today()
        else:
            selected_date = datetime.date.today()

        context["selected_date"] = selected_date
        context["availability"] = get_availability_for_date(space, selected_date)
        context["is_htmx"] = self.request.headers.get("HX-Request") == "true"
        return context

    def get_template_names(self):
        """Return partial template for HTMX requests."""
        if self.request.headers.get("HX-Request") == "true":
            return ["spaces/_availability.html"]
        return [self.template_name]
