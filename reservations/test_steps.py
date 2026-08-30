"""Tests for the reservation flow stepper.

O stepper é o componente que diz ao usuário onde ele está na jornada. Se ele
mostrar uma etapa que a aplicação não tem, promete um fluxo inexistente — por
isso os testes cobrem tanto a marcação quanto a coerência com o fluxo real.
"""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from reservations.steps import FLUXO_EM_USO, FLUXO_V2, contexto_do_stepper
from spaces.models import Space

User = get_user_model()


class TestContextoDoStepper:
    """The context builder resolves step state so the template stays dumb."""

    def test_marks_the_current_step(self):
        """Exatamente uma etapa é a atual."""
        contexto = contexto_do_stepper(2)
        atuais = [e for e in contexto["etapas"] if e["atual"]]
        assert len(atuais) == 1
        assert atuais[0]["numero"] == 2

    def test_marks_previous_steps_as_done(self):
        """Etapas anteriores aparecem como concluídas; as seguintes, não."""
        contexto = contexto_do_stepper(3)
        por_numero = {e["numero"]: e for e in contexto["etapas"]}
        assert por_numero[1]["concluida"] is True
        assert por_numero[2]["concluida"] is True
        assert por_numero[3]["concluida"] is False

    def test_first_step_has_nothing_done(self):
        """Na primeira etapa nada foi concluído ainda."""
        contexto = contexto_do_stepper(1)
        assert not any(e["concluida"] for e in contexto["etapas"])

    def test_total_matches_the_flow(self):
        """O total exibido acompanha o fluxo em uso."""
        assert contexto_do_stepper(1)["total_etapas"] == len(FLUXO_EM_USO)

    def test_existe_uma_lista_so(self):
        """``FLUXO_V2`` é apelido, não uma segunda lista.

        Durante um tempo foram duas — uma "em uso" e uma "alvo" — e as views
        migraram para a alvo sem que ninguém apagasse a outra. A constante morta
        continuou parecendo viva e a tela de Ajuda foi escrita a partir dela, o
        que fez a Ajuda ensinar três etapas enquanto o stepper mostrava quatro.

        Este teste existe para que duas listas não voltem por descuido.
        """
        assert FLUXO_V2 is FLUXO_EM_USO

    def test_o_fluxo_em_uso_e_o_de_quatro_etapas(self):
        """A jornada no ar é a do redesign V2, com detalhes e revisão."""
        assert len(FLUXO_EM_USO) == 4
        assert FLUXO_EM_USO[2].rotulo == "Detalhes e serviços"
        assert FLUXO_EM_USO[3].rotulo == "Revisão e confirmação"


class TestRenderizacaoDoStepper:
    """The rendered markup must be usable by a screen reader, not just by eye."""

    def test_marks_the_current_step_for_assistive_technology(self):
        """`aria-current="step"` é o que comunica a posição sem depender de cor."""
        html = render_to_string("components/_reservation_steps.html", contexto_do_stepper(2))
        assert html.count('aria-current="step"') == 1

    def test_states_are_described_in_text(self):
        """Concluída e atual precisam existir como texto, não só como cor."""
        html = render_to_string("components/_reservation_steps.html", contexto_do_stepper(2))
        assert "concluída" in html
        assert "atual" in html
        assert f"Etapa 1 de {len(FLUXO_EM_USO)}" in html

    def test_uses_an_ordered_list(self):
        """A ordem das etapas é informação e precisa estar na estrutura."""
        html = render_to_string("components/_reservation_steps.html", contexto_do_stepper(1))
        assert "<ol" in html
        assert html.count("<li") >= len(FLUXO_EM_USO)

    def test_renders_every_label_of_the_flow(self):
        """Nenhuma etapa some da renderização."""
        html = render_to_string("components/_reservation_steps.html", contexto_do_stepper(1))
        for etapa in FLUXO_EM_USO:
            assert etapa.rotulo in html


@pytest.mark.django_db
class TestStepperNasTelas:
    """Each screen of the flow announces its own position."""

    @pytest.fixture
    def usuario(self):
        """Create a logged-in regular user."""
        return User.objects.create_user(username="stepper", password="senha-de-teste")

    @pytest.fixture
    def espaco(self):
        """Create an active space."""
        return Space.objects.create(name="Sala Stepper", capacity=6, location="Bloco A")

    def test_space_list_is_step_one(self, client, usuario):
        """/spaces/ é a etapa 1 — escolher espaço."""
        client.force_login(usuario)
        response = client.get("/spaces/")
        assert response.status_code == 200
        assert response.context["etapa_atual"] == 1

    def test_space_detail_is_step_two(self, client, usuario, espaco):
        """/spaces/{id}/ é a etapa 2 — data e horário."""
        client.force_login(usuario)
        response = client.get(f"/spaces/{espaco.id}/")
        assert response.status_code == 200
        assert response.context["etapa_atual"] == 2

    def test_reservation_form_is_step_three(self, client, usuario, espaco):
        """/reservations/new/ é a etapa 3 — detalhes e serviços."""
        client.force_login(usuario)
        response = client.get(f"/reservations/new/?space={espaco.id}")
        assert response.status_code == 200
        assert response.context["etapa_atual"] == 3

    def test_reservation_form_keeps_the_stepper_on_error(self, client, usuario, espaco):
        """Erro de validação não pode fazer o usuário perder a referência do fluxo."""
        client.force_login(usuario)
        response = client.post(
            "/reservations/new/",
            {
                "space": espaco.id,
                "date": "data-invalida",
                "start_time": "10:00",
                "end_time": "11:00",
            },
        )
        assert response.status_code == 200
        assert response.context["etapa_atual"] == 3
        assert response.context["error"]
