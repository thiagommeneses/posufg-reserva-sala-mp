"""URL configuration for admin_dashboard app."""

from django.urls import path

from .views import (
    AdminDashboardView,
    AdminMaintenanceClassifyView,
    AdminMaintenanceCreateView,
    AdminMaintenanceDeleteView,
    AdminMaintenanceListView,
    AdminReservationCancelView,
    AdminReservationListView,
    AdminSpaceCreateView,
    AdminSpaceListView,
    AdminSpaceToggleView,
    AdminSpaceUpdateView,
    AdminUserCreateView,
    AdminUserDeleteView,
    AdminUserListView,
    AdminUserUpdateView,
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
    path(
        "maintenance/",
        AdminMaintenanceListView.as_view(),
        name="maintenance_list",
    ),
    path(
        "maintenance/new/",
        AdminMaintenanceCreateView.as_view(),
        name="maintenance_create",
    ),
    path(
        "maintenance/classify/",
        AdminMaintenanceClassifyView.as_view(),
        name="maintenance_classify",
    ),
    path(
        "maintenance/<int:pk>/delete/",
        AdminMaintenanceDeleteView.as_view(),
        name="maintenance_delete",
    ),
    path("users/", AdminUserListView.as_view(), name="user_list"),
    path("users/new/", AdminUserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/", AdminUserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/delete/", AdminUserDeleteView.as_view(), name="user_delete"),
]
