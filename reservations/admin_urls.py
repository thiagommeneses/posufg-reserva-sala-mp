"""URL configuration for admin-only reservation API endpoints."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MaintenanceBlockViewSet, OccupancyView

router = DefaultRouter()
router.register("maintenance-blocks", MaintenanceBlockViewSet, basename="maintenanceblock")

urlpatterns = router.urls + [
    path("occupancy/", OccupancyView.as_view(), name="occupancy"),
]
