"""URL configuration for admin-only reservation API endpoints."""

from rest_framework.routers import DefaultRouter

from .views import MaintenanceBlockViewSet

router = DefaultRouter()
router.register("maintenance-blocks", MaintenanceBlockViewSet, basename="maintenanceblock")

urlpatterns = router.urls
