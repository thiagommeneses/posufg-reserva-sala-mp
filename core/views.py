"""Core application views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from core.dashboard import (
    espacos_para_repetir,
    informacoes_uteis,
    proxima_reserva,
    proximas_reservas,
)
from reservations.models import BookingPolicy
from reservations.services import pode_fazer_check_in


def home_view(request):
    """Send the visitor to the home screen."""
    from django.shortcuts import redirect

    return redirect("inicio")


class InicioView(LoginRequiredMixin, View):
    """The user's home screen.

    Reúne, numa consulta por bloco, o que a pessoa precisa para agir: a reserva
    iminente (com check-in quando cabível), as seguintes, um atalho para repetir
    um espaço já usado e as regras que valem hoje.

    Não há contador de reservas nem gráfico de uso: o pacote V2 proíbe KPI de
    vaidade, e nenhum deles ajudaria alguém a conseguir uma sala.
    """

    template_name = "core/inicio.html"

    def get(self, request):
        """Render the home screen."""
        agora = timezone.now()
        proxima = proxima_reserva(request.user, agora)
        politica = BookingPolicy.carregar()

        return render(
            request,
            self.template_name,
            {
                "proxima": proxima,
                "pode_check_in": pode_fazer_check_in(proxima, agora) if proxima else False,
                "proximas": proximas_reservas(request.user, agora),
                "espacos_recentes": espacos_para_repetir(request.user),
                "informacoes": informacoes_uteis(politica),
                "agora": agora,
            },
        )


class AjudaView(LoginRequiredMixin, View):
    """A tela de Ajuda: metade derivada das regras, metade escrita por gente.

    As perguntas frequentes saem de :func:`core.ajuda.perguntas_frequentes`, que
    lê a política vigente — não há texto de regra digitado nesta tela. Os blocos
    institucionais saem de :class:`core.models.HelpArticle`, escritos pela
    administração, e só os publicados aparecem.

    Não há seção de contato. O pacote V2 pede "contato institucional real, se
    existir", e ele não existe no sistema: um telefone ou e-mail inventado numa
    tela de ajuda é pior do que a ausência dele. No lugar, a tela encaminha para
    Consultar Normas, que é um destino real e vivo.
    """

    template_name = "core/ajuda.html"

    def get(self, request):
        """Render the help screen."""
        from core.ajuda import perguntas_frequentes
        from core.models import HelpArticle

        return render(
            request,
            self.template_name,
            {
                "perguntas": perguntas_frequentes(),
                "blocos": HelpArticle.objects.publicados(),
            },
        )


class HtmxTestView(View):
    """A simple view to verify HTMX partial swaps work correctly."""

    def get(self, request):
        """Return full page or partial depending on HTMX request."""
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<div id="htmx-test-target" class="notice notice-success">'
                "HTMX partial swap works!"
                "</div>"
            )
        return render(request, "core/htmx_test.html")
