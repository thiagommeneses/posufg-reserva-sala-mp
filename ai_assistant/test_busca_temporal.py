"""Tests for the temporal half of the natural-language room search.

Um modelo de linguagem devolve texto plausível, não verdade. Todo valor que ele
propõe passa por validação deste lado antes de virar filtro — e, quando é
recusado, a razão vira aviso na tela. Silêncio aqui deixaria o resumo dizendo
"amanhã" enquanto a tela mostra hoje.

Nada nestes testes chama a API do Groq: ``_run_json_completion`` é substituído,
e o que se verifica é a fronteira entre o que o modelo diz e o que o sistema
aceita.
"""

import datetime
from unittest.mock import patch

import pytest

from ai_assistant.services import _prompt_de_busca, extract_room_search_filters

HOJE = datetime.date(2026, 8, 26)  # uma quarta-feira

CONTEXTO = {
    "hoje": HOJE.isoformat(),
    "hoje_date": HOJE,
    "dia_da_semana": "quarta-feira",
    "abertura": "08:00",
    "abertura_time": datetime.time(8, 0),
    "fechamento": "18:00",
    "fechamento_time": datetime.time(18, 0),
    "horizonte": 90,
    "duracao_minima": 30,
    "duracao_maxima": 240,
}


def resposta(**campos):
    """Build a fake LLM payload with sensible defaults.

    Args:
        **campos: Campos a sobrescrever.

    Returns:
        dict: Payload no formato que o modelo devolve.
    """
    base = {
        "min_capacity": None,
        "max_capacity": None,
        "attributes": [],
        "location": None,
        "summary": "",
        "date": None,
        "start_time": None,
        "duration_minutes": None,
    }
    base.update(campos)
    return base


class TestPrompt:
    """What the model is told."""

    def test_sem_contexto_nao_pede_campos_de_tempo(self):
        """Perguntar por data sem dizer que dia é hoje só produziria chute."""
        prompt = _prompt_de_busca()
        assert "start_time" not in prompt
        assert "duration_minutes" not in prompt

    def test_com_contexto_informa_a_data_de_hoje(self):
        """Uma expressão como "amanhã" não significa nada sem uma referência."""
        prompt = _prompt_de_busca(CONTEXTO)
        assert "2026-08-26" in prompt
        assert "quarta-feira" in prompt

    def test_com_contexto_informa_o_expediente(self):
        """Sem a janela real, "de manhã" viraria palpite."""
        prompt = _prompt_de_busca(CONTEXTO)
        assert "08:00" in prompt
        assert "18:00" in prompt

    def test_proibe_inventar_duracao(self):
        """Duração inventada vira uma reserva que a pessoa não pediu."""
        assert "não invente duração" in _prompt_de_busca(CONTEXTO)


class TestExtracaoTemporal:
    """What the system accepts from what the model proposes."""

    @patch("ai_assistant.services._run_json_completion")
    def test_sem_contexto_o_comportamento_e_o_de_antes(self, completacao):
        """Quem não passa contexto continua recebendo o mesmo de sempre."""
        completacao.return_value = resposta(min_capacity=8, date="2026-08-27")
        resultado = extract_room_search_filters("sala para 8 pessoas")
        assert resultado["min_capacity"] == 8
        assert resultado["date"] is None
        assert resultado["start_time"] is None
        assert resultado["avisos"] == []

    @patch("ai_assistant.services._run_json_completion")
    def test_aceita_data_valida(self, completacao):
        """O caso normal: "amanhã" vira uma data."""
        completacao.return_value = resposta(date="2026-08-27")
        resultado = extract_room_search_filters("sala amanhã", CONTEXTO)
        assert resultado["date"] == datetime.date(2026, 8, 27)
        assert resultado["avisos"] == []

    @patch("ai_assistant.services._run_json_completion")
    def test_recusa_data_no_passado_e_avisa(self, completacao):
        """Descartar em silêncio deixaria o resumo prometendo o impossível."""
        completacao.return_value = resposta(date="2020-01-01")
        resultado = extract_room_search_filters("sala ontem", CONTEXTO)
        assert resultado["date"] is None
        assert any("passou" in aviso for aviso in resultado["avisos"])

    @patch("ai_assistant.services._run_json_completion")
    def test_recusa_data_alem_do_horizonte_e_avisa(self, completacao):
        """A regra de antecedência é do sistema, não do modelo."""
        completacao.return_value = resposta(date="2030-01-01")
        resultado = extract_room_search_filters("sala em 2030", CONTEXTO)
        assert resultado["date"] is None
        assert any("antecedência" in aviso for aviso in resultado["avisos"])

    @patch("ai_assistant.services._run_json_completion")
    def test_aceita_o_ultimo_dia_do_horizonte(self, completacao):
        """O limite é inclusivo."""
        limite = HOJE + datetime.timedelta(days=CONTEXTO["horizonte"])
        completacao.return_value = resposta(date=limite.isoformat())
        assert extract_room_search_filters("sala", CONTEXTO)["date"] == limite

    @patch("ai_assistant.services._run_json_completion")
    def test_data_malformada_nao_quebra(self, completacao):
        """Um modelo pode devolver qualquer coisa; a tela não pode cair."""
        completacao.return_value = resposta(date="quinta que vem")
        resultado = extract_room_search_filters("sala", CONTEXTO)
        assert resultado["date"] is None
        assert resultado["avisos"]

    @patch("ai_assistant.services._run_json_completion")
    def test_aceita_horario_dentro_do_expediente(self, completacao):
        """O caso normal."""
        completacao.return_value = resposta(start_time="14:30")
        resultado = extract_room_search_filters("sala às 14h30", CONTEXTO)
        assert resultado["start_time"] == datetime.time(14, 30)

    @patch("ai_assistant.services._run_json_completion")
    def test_recusa_horario_fora_do_expediente_e_avisa(self, completacao):
        """Oferecer 22h seria oferecer o que o prédio não abre."""
        completacao.return_value = resposta(start_time="22:00")
        resultado = extract_room_search_filters("sala às 22h", CONTEXTO)
        assert resultado["start_time"] is None
        assert any("expediente" in aviso for aviso in resultado["avisos"])

    @patch("ai_assistant.services._run_json_completion")
    def test_horario_de_fechamento_e_recusado(self, completacao):
        """Às 18:00 o expediente termina; não há o que começar."""
        completacao.return_value = resposta(start_time="18:00")
        assert extract_room_search_filters("sala", CONTEXTO)["start_time"] is None

    @patch("ai_assistant.services._run_json_completion")
    def test_aceita_duracao_permitida(self, completacao):
        """Duas horas está dentro dos limites da política."""
        completacao.return_value = resposta(duration_minutes=120)
        assert extract_room_search_filters("sala por 2h", CONTEXTO)["duration_minutes"] == 120

    @patch("ai_assistant.services._run_json_completion")
    def test_recusa_duracao_fora_dos_limites_sem_arredondar(self, completacao):
        """Encurtar a reunião de alguém sem avisar é pior do que ignorar o pedido."""
        completacao.return_value = resposta(duration_minutes=600)
        resultado = extract_room_search_filters("sala o dia todo", CONTEXTO)
        assert resultado["duration_minutes"] is None
        assert any("duração" in aviso for aviso in resultado["avisos"])

    @patch("ai_assistant.services._run_json_completion")
    def test_duracao_curta_demais_tambem_e_recusada(self, completacao):
        """Abaixo da duração mínima nenhuma reserva seria aceita."""
        completacao.return_value = resposta(duration_minutes=5)
        assert extract_room_search_filters("sala", CONTEXTO)["duration_minutes"] is None

    @patch("ai_assistant.services._run_json_completion")
    def test_campos_de_capacidade_continuam_funcionando(self, completacao):
        """A extensão não pode ter mexido no que já existia."""
        completacao.return_value = resposta(
            min_capacity=8, attributes=["internet"], location="Bloco A", summary="ok"
        )
        resultado = extract_room_search_filters("sala", CONTEXTO)
        assert resultado["min_capacity"] == 8
        assert resultado["attributes"] == ["Wi-Fi"]
        assert resultado["location"] == "Bloco A"
        assert resultado["summary"] == "ok"

    @patch("ai_assistant.services._run_json_completion")
    def test_pedido_sem_tempo_nao_gera_aviso(self, completacao):
        """Quem não falou de horário não precisa ler nada sobre horário."""
        completacao.return_value = resposta(min_capacity=8)
        assert extract_room_search_filters("sala para 8", CONTEXTO)["avisos"] == []


@pytest.mark.django_db
class TestContextoTemporal:
    """The facts handed to the assistant, built from the real policy."""

    def test_sai_da_politica_vigente(self):
        """Mudar a política muda o que o assistente sabe."""
        from reservations.availability import contexto_temporal
        from reservations.models import BookingPolicy

        politica = BookingPolicy.carregar()
        politica.opening_time = datetime.time(7, 0)
        politica.horizon_days = 30
        politica.save()

        contexto = contexto_temporal(hoje=HOJE)
        assert contexto["abertura"] == "07:00"
        assert contexto["horizonte"] == 30

    def test_dia_da_semana_em_portugues(self):
        """O ``%A`` do sistema devolveria "Wednesday" no contêiner."""
        from reservations.availability import contexto_temporal

        assert contexto_temporal(hoje=HOJE)["dia_da_semana"] == "quarta-feira"

    def test_traz_tudo_que_o_prompt_precisa(self):
        """Um campo faltando quebraria a formatação do prompt."""
        from reservations.availability import contexto_temporal

        contexto = contexto_temporal(hoje=HOJE)
        _prompt_de_busca(contexto)  # não pode levantar KeyError
        assert contexto["hoje_date"] == HOJE
