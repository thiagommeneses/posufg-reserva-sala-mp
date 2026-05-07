"""Core application URL configuration."""

from django.urls import path

from .views import HtmxTestView, home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("htmx-test/", HtmxTestView.as_view(), name="htmx_test"),
]
