"""Periodic jobs runner — the process that makes scheduled rules actually happen.

Até aqui ``release_no_shows`` existia como comando e nada o executava: a regra
de no-show estava escrita, testada e **nunca acontecia**. Este comando é o laço
que a executa.

Por que um laço e não cron: o contêiner da aplicação roda um processo só, e pôr
um cron dentro dele exigiria um supervisor. Por que não Celery: um agendador de
uma tarefa a cada poucos minutos não justifica um broker, uma fila e dois
processos a mais para manter. O ``docker compose`` já sabe reiniciar um serviço
que morre, que é a única garantia que este laço precisa.

Um erro numa passada não derruba o laço — a passada seguinte tenta de novo.
Derrubar o processo por causa de um banco que piscou faria o agendador parar
justamente quando a aplicação mais precisa que ele continue.
"""

import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from reservations.services import auto_release_no_shows

#: Com que frequência o laço acorda. Cinco minutos é mais fino do que a menor
#: tolerância que faz sentido configurar e grosso o bastante para não pesar.
INTERVALO_PADRAO_SEGUNDOS = 300


class Command(BaseCommand):
    """Run the periodic jobs in a loop, until the process is stopped."""

    help = "Executa as rotinas periódicas (liberação de no-show) em laço."

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--intervalo",
            type=int,
            default=INTERVALO_PADRAO_SEGUNDOS,
            help=f"Segundos entre passadas (padrão: {INTERVALO_PADRAO_SEGUNDOS}).",
        )
        parser.add_argument(
            "--passadas",
            type=int,
            default=0,
            help="Quantas passadas executar antes de sair. Zero (padrão) roda para sempre.",
        )

    def handle(self, *args, **options):
        """Run the loop."""
        intervalo = options["intervalo"]
        limite = options["passadas"]

        self.stdout.write(
            self.style.SUCCESS(f"Agendador iniciado — uma passada a cada {intervalo}s.")
        )

        passada = 0
        while True:
            passada += 1
            self._executar_passada()
            if limite and passada >= limite:
                break
            time.sleep(intervalo)

    def _executar_passada(self):
        """Run every job once, letting no single failure stop the loop."""
        try:
            liberadas = auto_release_no_shows()
        except Exception as exc:  # noqa: BLE001 - o laço não pode morrer por uma passada
            # ``connection.close()`` porque a causa mais comum de falha aqui é
            # uma conexão que o banco derrubou por ociosidade: fechá-la faz o
            # Django abrir outra na passada seguinte, em vez de reusar a morta.
            connection.close()
            self.stderr.write(self.style.WARNING(f"Passada falhou e será repetida: {exc}"))
            return

        if liberadas:
            agora = timezone.localtime().strftime("%d/%m %H:%M")
            self.stdout.write(
                f"{agora} — {liberadas} reserva(s) liberada(s) por não comparecimento."
            )
