"""URL configuration for the spaces app API."""

from rest_framework.routers import DefaultRouter

from .views import SpaceViewSet

router = DefaultRouter()
router.register("spaces", SpaceViewSet, basename="space")

urlpatterns = router.urls
