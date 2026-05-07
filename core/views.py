"""Core application views."""

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View


class HtmxTestView(View):
    """A simple view to verify HTMX partial swaps work correctly."""

    def get(self, request):
        """Return full page or partial depending on HTMX request."""
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<div id="htmx-test-target" class="alert alert-success">'
                "HTMX partial swap works!"
                "</div>"
            )
        return render(request, "core/htmx_test.html")
