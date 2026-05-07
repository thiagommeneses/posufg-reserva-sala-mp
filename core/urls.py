"""Core application URL configuration."""

from django.urls import path

from .views import HtmxTestView

urlpatterns = [
    path("htmx-test/", HtmxTestView.as_view(), name="htmx_test"),
]
