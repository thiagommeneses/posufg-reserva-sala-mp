"""Management command to seed the database with default demo data."""

from django.core.management.base import BaseCommand

from core.seeds import attributes, maintenance, reservations, spaces, users


class Command(BaseCommand):
    """Seed the database with default data for development and demonstration."""

    help = "Populate the database with default demo data in Portuguese (pt-BR)."

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Remove existing seed data before re-seeding.",
        )

    def handle(self, *args, **options):
        """Orchestrate seed modules in dependency order."""
        flush = options["flush"]

        if flush:
            self.stdout.write(self.style.WARNING("Flushing seed data..."))
            # Reverse order to respect FK constraints
            maintenance.flush()
            reservations.flush()
            users.flush()
            spaces.flush()
            attributes.flush()
            self.stdout.write(self.style.SUCCESS("Seed data flushed."))

        self.stdout.write("Seeding attributes...")
        attributes.seed()
        self.stdout.write(self.style.SUCCESS("Attributes seeded."))

        self.stdout.write("Seeding spaces...")
        spaces.seed()
        self.stdout.write(self.style.SUCCESS("Spaces seeded."))

        self.stdout.write("Seeding users...")
        users.seed()
        self.stdout.write(self.style.SUCCESS("Users seeded."))

        self.stdout.write("Seeding reservations...")
        reservations.seed()
        self.stdout.write(self.style.SUCCESS("Reservations seeded."))

        self.stdout.write("Seeding maintenance blocks...")
        maintenance.seed()
        self.stdout.write(self.style.SUCCESS("Maintenance blocks seeded."))

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
