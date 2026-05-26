"""Management command to release no-show reservations."""

from django.core.management.base import BaseCommand

from reservations.services import auto_release_no_shows


class Command(BaseCommand):
    """Mark overdue confirmed reservations as no-show."""

    help = "Release no-show reservations that have passed the check-in threshold"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--threshold",
            type=int,
            default=15,
            help=(
                "Number of minutes after start_time to wait before marking as no-show (default: 15)"
            ),
        )

    def handle(self, *args, **options):
        """Run the auto-release logic."""
        threshold = options["threshold"]
        released_count = auto_release_no_shows(threshold_minutes=threshold)
        self.stdout.write(
            self.style.SUCCESS(
                f"Released {released_count} no-show reservation(s) "
                f"(threshold: {threshold} minutes)",
            )
        )
