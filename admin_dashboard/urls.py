"""URL configuration for admin_dashboard app."""

from django.urls import path

from .views import (
    AdminDashboardView,
    AdminReservationCancelView,
    AdminReservationListView,
    AdminSpaceCreateView,
    AdminSpaceListView,
    AdminSpaceToggleView,
    AdminSpaceUpdateView,
)

app_name = "admin_dashboard"

urlpatterns = [
    path("", AdminDashboardView.as_view(), name="admin_dashboard"),
    path("spaces/", AdminSpaceListView.as_view(), name="space_list"),
    path("spaces/new/", AdminSpaceCreateView.as_view(), name="space_create"),
    path("spaces/<int:pk>/", AdminSpaceUpdateView.as_view(), name="space_update"),
    path("spaces/<int:pk>/toggle/", AdminSpaceToggleView.as_view(), name="space_toggle"),
    path("reservations/", AdminReservationListView.as_view(), name="reservation_list"),
    path(
        "reservations/<int:pk>/cancel/",
        AdminReservationCancelView.as_view(),
        name="reservation_cancel",
    ),
]
