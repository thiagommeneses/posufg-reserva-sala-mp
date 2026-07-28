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
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions as drf_permissions

from knowledge.views import DocumentAssistantView
from reservations.views import (
    ReservationCancelView,
    ReservationCheckInView,
    ReservationCreateView,
    ReservationDetailView,
    ReservationListView,
    ReservationRescheduleView,
)
from spaces.views import SpaceDetailView, SpaceListView

schema_view = get_schema_view(
    openapi.Info(
        title="Sistema de Reserva de Espaços API",
        default_version="v1",
        description=(
            "API REST para reserva de salas e assistentes de IA "
            "(busca de salas em linguagem natural e classificação de manutenção)."
        ),
        contact=openapi.Contact(email="rogerior@ufg.br"),
    ),
    public=True,
    permission_classes=[drf_permissions.AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("spaces.urls")),
    path("api/v1/", include("reservations.urls")),
    path("api/v1/admin/", include("reservations.admin_urls")),
    path("api/v1/", include("rest_framework.urls", namespace="rest_framework")),
    path("api/v1/", include("ai_assistant.urls")),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
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
    path("assistente/", DocumentAssistantView.as_view(), name="document_assistant"),
    path("admin-dashboard/", include("admin_dashboard.urls")),
    path("", include("core.urls")),
]
