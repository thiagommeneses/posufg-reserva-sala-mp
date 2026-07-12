"""URL configuration for the ai_assistant app API."""

from django.urls import path

from ai_assistant.views import MaintenanceReasonClassifierView, RoomSearchAssistantView

urlpatterns = [
    path("ai/room-search/", RoomSearchAssistantView.as_view(), name="ai-room-search"),
    path(
        "ai/maintenance-classify/",
        MaintenanceReasonClassifierView.as_view(),
        name="ai-maintenance-classify",
    ),
]
