"""Management command to release no-show reservations, one pass only.

O laço que executa isto de forma contínua é ``agendador``. Este comando existe
para a passada manual: conferir quantas reservas seriam liberadas, ou liberar à
mão sem esperar o agendador.
"""

from django.core.management.base import BaseCommand

from reservations.models import BookingPolicy
from reservations.services import auto_release_no_shows


class Command(BaseCommand):
    """Mark overdue confirmed reservations as no-show."""

    help = "Libera reservas confirmadas sem check-in que passaram da tolerância."

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--threshold",
            type=int,
            default=None,
            help="Tolerância em minutos. Sem isto, usa a configurada na política.",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help=(
                "Executa mesmo com a regra desligada na política. "
                "Use sabendo que isto marca reservas de gente que pode ter comparecido."
            ),
        )

    def handle(self, *args, **options):
        """Run the auto-release logic once."""
        policy = BookingPolicy.carregar()
        if not policy.release_no_shows and not options["forcar"]:
            self.stdout.write(
                self.style.WARNING(
                    "A liberação por não comparecimento está desligada na política de "
                    "reserva. Ligue em /admin-dashboard/policy/ ou use --forcar."
                )
            )
            return

        liberadas = auto_release_no_shows(
            threshold_minutes=options["threshold"],
            respeitar_politica=not options["forcar"],
        )
        tolerancia = options["threshold"] or policy.no_show_threshold_minutes
        self.stdout.write(
            self.style.SUCCESS(
                f"{liberadas} reserva(s) liberada(s) (tolerância: {tolerancia} minutos)."
            )
        )
