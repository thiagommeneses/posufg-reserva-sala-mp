"""Core application URL configuration."""

from django.urls import path

from .views import AjudaView, HtmxTestView, InicioView, home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("inicio/", InicioView.as_view(), name="inicio"),
    path("ajuda/", AjudaView.as_view(), name="ajuda"),
    path("htmx-test/", HtmxTestView.as_view(), name="htmx_test"),
]
