"""URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from reservations.views import (
    ReservationCancelView,
    ReservationCheckInView,
    ReservationCreateView,
    ReservationDetailView,
    ReservationListView,
    ReservationRescheduleView,
)
from spaces.views import SpaceDetailView, SpaceListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("spaces.urls")),
    path("api/", include("reservations.urls")),
    path("api/admin/", include("reservations.admin_urls")),
    path("api/", include("rest_framework.urls", namespace="rest_framework")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("spaces/", SpaceListView.as_view(), name="space_list"),
    path("spaces/<int:pk>/", SpaceDetailView.as_view(), name="space_detail"),
    path("reservations/", ReservationListView.as_view(), name="reservation_list"),
    path("reservations/new/", ReservationCreateView.as_view(), name="reservation_create"),
    path("reservations/<int:pk>/", ReservationDetailView.as_view(), name="reservation_detail"),
    path(
        "reservations/<int:pk>/cancel/", ReservationCancelView.as_view(), name="reservation_cancel"
    ),
    path(
        "reservations/<int:pk>/reschedule/",
        ReservationRescheduleView.as_view(),
        name="reservation_reschedule",
    ),
    path(
        "reservations/<int:pk>/check-in/",
        ReservationCheckInView.as_view(),
        name="reservation_checkin",
    ),
    path("", include("core.urls")),
]
