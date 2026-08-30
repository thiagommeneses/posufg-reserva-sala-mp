"""URL configuration for accounts app."""

from django.urls import path

from accounts.views import login_view, logout_view, profile_view, register_view

app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("profile/", profile_view, name="profile"),
    path("logout/", logout_view, name="logout"),
]
