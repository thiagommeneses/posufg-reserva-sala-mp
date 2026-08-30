"""Core application tests."""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from reservations.services import (
    auto_release_no_shows,
    check_in_reservation,
    create_reservation,
    get_availability_for_date,
)
from spaces.models import Attribute, Space


class SmokeTestCase(TestCase):
    """Basic smoke test to verify Django and pytest integration."""

    def test_settings_loaded(self):
        """Verify that Django settings module is loaded."""
        from django.conf import settings

        assert settings.DEBUG is not None


class TemplateInfrastructureTestCase(TestCase):
    """Tests for template infrastructure, HTMX, DaisyUI, and Tailwind setup."""

    def test_base_template_contains_tailwind_stylesheet(self):
        """Verify base.html includes the compiled Tailwind CSS bundle."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, "tailwind.css")

    def test_base_template_loads_htmx_from_local_static(self):
        """Verify base.html serves HTMX from static files, not from a public CDN.

        Em rede institucional com egress restrito a CDN pública falhava e a
        aplicação perdia toda a interatividade, então o arquivo passou a ser
        servido pela própria aplicação.
        """
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, "js/htmx.min.js")
        self.assertNotContains(response, "unpkg.com")
        self.assertNotContains(response, "cdn.jsdelivr.net")

    def test_base_template_has_theme_attribute(self):
        """Verify base.html has DaisyUI theme data-theme attribute."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, 'data-theme="mpgo"')

    def test_htmx_test_view_returns_full_page(self):
        """Verify HTMX test view returns full HTML page for regular requests."""
        response = self.client.get(reverse("htmx_test"))
        assert response.status_code == 200
        assert "<html" in response.content.decode()
        assert "HTMX Test Page" in response.content.decode()

    def test_htmx_test_view_returns_partial(self):
        """Verify HTMX test view returns partial for HX-Request header."""
        response = self.client.get(
            reverse("htmx_test"),
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "<html" not in response.content.decode()
        assert "HTMX partial swap works!" in response.content.decode()
        assert 'id="htmx-test-target"' in response.content.decode()

    def test_base_user_template_renders_navbar(self):
        """Verify base_user.html contains the shell and the working destinations."""
        from django.template.loader import render_to_string

        html = render_to_string("base_user.html", {})
        assert "Reserva de Espaços" in html
        assert "Início" in html
        assert "Nova Reserva" in html
        assert "Minhas Reservas" in html
        assert "Consultar Normas" in html
        assert "Sair" in html
        assert "navbar" in html
        assert "drawer" in html
        assert "sidebar-link" in html
        # Seções do redesign V2
        assert "Reservas" in html
        assert "Informações" in html

    def test_user_sidebar_has_no_dead_entries(self):
        """No menu entry may point to a screen that does not exist yet.

        A lista encolheu de novo: "Calendário" saiu na Fase 19 e "Ajuda" na
        Fase 23, cada um quando a tela passou a existir. Sobram os itens que o
        redesign prevê e o sistema ainda não tem — item que leva a lugar nenhum
        é pior do que item ausente.

        A guarda que não depende de alguém manter esta lista é
        ``test_every_sidebar_link_resolves_to_a_real_url``.
        """
        from django.template.loader import render_to_string

        html = render_to_string("base_user.html", {})
        for ainda_nao_existe in ["Relatórios", "Configurações"]:
            assert ainda_nao_existe not in html, (
                f"{ainda_nao_existe!r} está no menu do usuário mas não tem tela"
            )

    def test_user_sidebar_has_ajuda(self):
        """Ajuda existe desde a Fase 23 e precisa estar no menu, com rota viva."""
        from django.template.loader import render_to_string
        from django.urls import Resolver404, resolve

        html = render_to_string("base_user.html", {})
        assert "Ajuda" in html, "a tela existe desde a Fase 23 e precisa estar no menu"
        try:
            resolve("/ajuda/")
        except Resolver404:  # pragma: no cover - só dispara em regressão
            raise AssertionError("Ajuda está no menu mas a rota sumiu") from None

    def test_base_admin_template_renders_sidebar(self):
        """Verify base_admin.html contains expected sidebar elements."""
        from django.template.loader import render_to_string

        html = render_to_string("base_admin.html", {})
        assert "Admin" in html
        assert "Visão Geral" in html
        assert "Espaços" in html
        assert "Reservas" in html
        assert "Manutenção" in html
        assert "Tipos de Espaço" in html
        assert "Equipamentos" in html
        assert "Política de reserva" in html
        assert "Usuários" in html
        assert "Serviços" in html
        assert "Catálogo de Serviços" in html
        assert "drawer" in html
        assert "sidebar-link" in html

    def test_admin_sidebar_has_no_dead_entries(self):
        """Todo item do menu admin aponta para uma tela que existe.

        A lista de proibidos esvaziou: "Calendário Geral" saiu na Fase 19b e
        "Relatórios" na Fase 22b, quando cada tela passou a existir. A guarda
        de verdade é ``test_every_sidebar_link_resolves_to_a_real_url``, que não
        depende de alguém lembrar de manter uma lista.
        """
        from django.template.loader import render_to_string
        from django.urls import Resolver404, resolve

        html = render_to_string("base_admin.html", {})
        assert "Relatórios" in html, "a tela existe desde a Fase 22b e precisa estar no menu"
        try:
            resolve("/admin-dashboard/relatorios/")
        except Resolver404:  # pragma: no cover - só dispara em regressão
            raise AssertionError("Relatórios está no menu mas a rota sumiu") from None

    def test_os_layouts_cortam_o_excesso_horizontal(self):
        """Both layouts must clip horizontal overflow — and with ``clip``.

        Guarda fraca de propósito: afirma sobre uma classe, porque a suíte não
        tem navegador para medir largura. Ela existe porque o defeito é caro de
        reencontrar — em 390px o documento ficava com 616px e um vazio branco à
        direita, sem erro nenhum no console — e porque a escolha entre ``clip``
        e ``hidden`` não é indiferente: ``hidden`` cria contexto de rolagem e
        faria o resumo fixo do passo 1 parar de grudar no rodapé.
        """
        from django.template.loader import render_to_string

        for template in ["base_user.html", "base_admin.html"]:
            html = render_to_string(template, {})
            assert "overflow-x-clip" in html, f"{template} não corta o excesso horizontal"
            assert "overflow-x-hidden" not in html, (
                f"{template} usa hidden, que quebraria o resumo fixo"
            )

    def test_every_sidebar_link_resolves_to_a_real_url(self):
        """Every href in both sidebars must resolve — no dead links, ever."""
        import re

        from django.template.loader import render_to_string
        from django.urls import Resolver404, resolve

        for template in ["base_user.html", "base_admin.html"]:
            html = render_to_string(template, {})
            # Só a sidebar: o <head> tem links para CSS e fontes, que são
            # arquivos servidos pelo staticfiles e não rotas do URLconf.
            sidebar = re.search(r"<aside\b.*?</aside>", html, re.S)
            assert sidebar, f"{template} não tem sidebar"
            hrefs = set(re.findall(r'href="(/[^"]*)"', sidebar.group(0)))
            assert hrefs, f"{template} não tem nenhum link na sidebar"
            for href in hrefs:
                try:
                    resolve(href)
                except Resolver404:  # pragma: no cover - só dispara em regressão
                    raise AssertionError(f"{template}: {href} não resolve") from None

    def test_messages_partial_renders_alerts(self):
        """Verify messages partial renders muted notice toasts."""
        from django.contrib.messages import constants
        from django.contrib.messages.storage.base import Message
        from django.template.loader import render_to_string

        messages = [
            Message(constants.SUCCESS, "Operation successful"),
            Message(constants.ERROR, "Something went wrong"),
        ]
        html = render_to_string("partials/_messages.html", {"messages": messages})
        assert "notice-success" in html
        assert "notice-error" in html
        assert "Operation successful" in html
        assert "Something went wrong" in html


class SeedDataCommandTestCase(TestCase):
    """Tests for the seed_data management command."""

    def test_command_runs_successfully(self):
        """Verify seed_data command completes without errors."""
        out = StringIO()
        call_command("seed_data", stdout=out)
        output = out.getvalue()
        assert "Database seeding completed successfully!" in output

    def test_command_is_idempotent(self):
        """Verify running seed_data twice does not duplicate records."""
        call_command("seed_data")
        attr_count_first = Attribute.objects.count()
        space_count_first = Space.objects.count()
        user_count_first = User.objects.count()
        reservation_count_first = Reservation.objects.count()
        block_count_first = MaintenanceBlock.objects.count()

        call_command("seed_data")

        assert Attribute.objects.count() == attr_count_first
        assert Space.objects.count() == space_count_first
        assert User.objects.count() == user_count_first
        assert Reservation.objects.count() == reservation_count_first
        assert MaintenanceBlock.objects.count() == block_count_first

    def test_command_is_idempotent_across_time(self):
        """Seeding twice is idempotent even when the clock moves between runs.

        Os horários das reservas e bloqueios derivam de ``timezone.now()``. Quando as
        duas execuções caíam em minutos diferentes, a segunda deixava de reconhecer os
        registros da primeira: reservas colidiam na exclusion constraint e bloqueios de
        manutenção eram duplicados em silêncio. A identidade passou a ser a chave
        natural (usuário+espaço, espaço+motivo), independente do relógio.
        """
        from datetime import timedelta
        from unittest.mock import patch

        call_command("seed_data")
        reservation_count = Reservation.objects.count()
        block_count = MaintenanceBlock.objects.count()

        agora = timezone.now()
        with patch("django.utils.timezone.now", return_value=agora + timedelta(minutes=7)):
            call_command("seed_data")

        assert Reservation.objects.count() == reservation_count
        assert MaintenanceBlock.objects.count() == block_count

    def test_flush_flag_removes_and_recreates(self):
        """Verify --flush removes seed data and recreates it."""
        call_command("seed_data")
        assert Attribute.objects.count() == 7
        assert Space.objects.count() == 5
        assert User.objects.filter(username="admin").exists()

        call_command("seed_data", flush=True)
        assert Attribute.objects.count() == 7
        assert Space.objects.count() == 5
        assert User.objects.filter(username="admin").exists()

    def test_command_creates_portuguese_content(self):
        """Verify seeded content is in Portuguese (pt-BR)."""
        call_command("seed_data")

        assert Attribute.objects.filter(name="Ar-condicionado").exists()
        assert Attribute.objects.filter(name="Videoconferência").exists()
        assert Space.objects.filter(name="Sala de Reunião Alfa").exists()
        assert Space.objects.filter(location="Térreo").exists()


@pytest.mark.django_db
class TestReservationLifecycleIntegration:
    """End-to-end integration tests for the reservation lifecycle."""

    def test_full_lifecycle_create_search_reserve_checkin(self, client):
        """Cover full lifecycle: create space, search by attributes, reserve, check-in."""
        attr = Attribute.objects.create(name="Projetor")
        space = Space.objects.create(
            name="Sala Integração",
            capacity=10,
            location="Térreo",
            is_active=True,
        )
        space.space_attributes.create(attribute=attr)

        user = User.objects.create_user(username="lifecycle_user", password="testpass123")
        client.login(username="lifecycle_user", password="testpass123")

        # Search spaces by attribute
        response = client.get("/spaces/", {"attributes": attr.name})
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert space in list(spaces)

        # Create reservation via API (start within check-in window)
        now = timezone.now()
        start = now - timezone.timedelta(minutes=5)
        end = now + timezone.timedelta(hours=1)
        response = client.post(
            "/api/v1/reservations/",
            {
                "space": space.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        reservation = Reservation.objects.get(pk=response.json()["id"])
        assert reservation.status == ReservationStatus.CONFIRMED

        # Check-in to reservation
        check_in_reservation(reservation, user)
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CHECKED_IN
        assert reservation.checked_in_at is not None

    def test_no_show_flow_auto_releases_slot(self):
        """Overdue reservation without check-in is marked no_show and slot frees up."""
        space = Space.objects.create(
            name="Sala No-show", capacity=5, location="1º andar", is_active=True
        )
        user = User.objects.create_user(username="noshow_user", password="testpass123")

        now = timezone.now()
        start = now - timezone.timedelta(hours=2)
        end = now - timezone.timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )

        # Verify slot is occupied before auto-release
        availability = get_availability_for_date(space, timezone.localdate(start))
        assert len(availability["occupied"]) > 0

        # A regra vem desligada na política; este teste é sobre o que ela faz
        # quando ligada, então liga.
        from reservations.models import BookingPolicy

        politica = BookingPolicy.carregar()
        politica.release_no_shows = True
        politica.save(update_fields=["release_no_shows"])

        released = auto_release_no_shows(threshold_minutes=15)
        assert released == 1

        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.NO_SHOW

        # Verify slot is now available
        availability = get_availability_for_date(space, timezone.localdate(start))
        assert len(availability["occupied"]) == 0

    def test_conflict_prevention_two_users_same_slot(self):
        """Two users trying to book the same slot: second one is rejected."""
        space = Space.objects.create(
            name="Sala Conflito", capacity=5, location="2º andar", is_active=True
        )
        user1 = User.objects.create_user(username="user1", password="testpass123")
        user2 = User.objects.create_user(username="user2", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)

        # User 1 books successfully
        res1 = create_reservation(user1, space, start, end)
        assert res1.status == ReservationStatus.CONFIRMED

        # User 2 tries to book the same slot and is rejected
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            create_reservation(user2, space, start, end)

    def test_cancel_and_rebook_frees_slot(self):
        """User cancels reservation, then another user successfully books the same slot."""
        space = Space.objects.create(
            name="Sala Rebook", capacity=5, location="3º andar", is_active=True
        )
        user1 = User.objects.create_user(username="canceler", password="testpass123")
        user2 = User.objects.create_user(username="rebooker", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)

        # User 1 creates reservation
        reservation = create_reservation(user1, space, start, end)
        assert Reservation.objects.filter(pk=reservation.pk).exists()

        # User 1 cancels reservation
        from reservations.services import cancel_reservation

        cancel_reservation(reservation, user1)
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

        # User 2 books the now-free slot
        res2 = create_reservation(user2, space, start, end)
        assert res2.status == ReservationStatus.CONFIRMED
        assert res2.pk != reservation.pk


@pytest.mark.django_db
class TestUserInterfaceFlow:
    """End-to-end tests for user-facing web interface flows."""

    def test_user_registers_logs_in_searches_creates_reservation(self, client):
        """Full user flow from registration to viewing reservation in list."""
        space = Space.objects.create(
            name="Sala UI Flow", capacity=8, location="Térreo", is_active=True
        )

        # Register
        response = client.post(
            "/accounts/register/",
            {
                "username": "uiflowuser",
                "email": "ui@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(username="uiflowuser")

        # Login
        client.login(username="uiflowuser", password="StrongPass123!")

        # Search spaces
        response = client.get("/spaces/")
        assert response.status_code == 200
        assert space in list(response.context["spaces"])

        # View space detail
        response = client.get(f"/spaces/{space.pk}/")
        assert response.status_code == 200
        assert response.context["space"] == space

        # Create reservation via web form.
        #
        # Data e horário fixos, e não derivados de ``timezone.now()``. A versão
        # anterior somava duas e três horas ao agora *em UTC* e postava a data
        # do início com a hora do término: entre 21h e 22h UTC o término caía no
        # dia seguinte, a data postada continuava sendo a do início, e o
        # formulário recusava por término anterior ao início. Falhava uma hora
        # por dia, e a sonda de fuso não via — ``timezone.now()`` é UTC
        # independentemente de ``TIME_ZONE``.
        amanha = timezone.localdate() + timezone.timedelta(days=1)
        response = client.post(
            "/reservations/new/",
            {
                "space": str(space.pk),
                "date": amanha.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                # Desde a Fase 10 o formulário exige assunto e participantes.
                "title": "Reunião do fluxo completo",
                "attendee_count": "2",
            },
        )
        assert response.status_code == 302
        reservation = Reservation.objects.get(user=user, space=space)
        assert reservation.status == ReservationStatus.CONFIRMED

        # View reservation in My Reservations
        response = client.get("/reservations/")
        assert response.status_code == 200
        assert reservation in list(response.context["reservations"])

    def test_user_cancels_reservation_via_web_interface(self, client):
        """User cancels reservation via web and slot becomes available again."""
        space = Space.objects.create(
            name="Sala Cancel UI", capacity=5, location="1º andar", is_active=True
        )
        user = User.objects.create_user(username="cancelui", password="testpass123")
        client.login(username="cancelui", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )

        # Verify slot is occupied before cancel
        availability = get_availability_for_date(space, timezone.localdate(start))
        assert len(availability["occupied"]) > 0

        # Cancel via web interface
        response = client.post(f"/reservations/{reservation.pk}/cancel/")
        assert response.status_code == 302

        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

        # Verify slot is now available
        availability = get_availability_for_date(space, timezone.localdate(start))
        assert len(availability["occupied"]) == 0

    def test_user_checks_in_via_direct_url(self, client):
        """User accesses check-in page via direct URL and check-in succeeds."""
        space = Space.objects.create(
            name="Sala Check-in UI", capacity=5, location="2º andar", is_active=True
        )
        user = User.objects.create_user(username="checkinui", password="testpass123")
        client.login(username="checkinui", password="testpass123")

        now = timezone.now()
        start = now - timezone.timedelta(minutes=5)
        end = now + timezone.timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )

        response = client.post(f"/reservations/{reservation.pk}/check-in/")
        assert response.status_code == 302

        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CHECKED_IN
        assert reservation.checked_in_at is not None

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users are redirected to login on all protected pages."""
        protected_urls = [
            "/spaces/",
            "/spaces/1/",
            "/reservations/",
            "/reservations/new/",
            "/reservations/1/",
            "/reservations/1/cancel/",
            "/reservations/1/reschedule/",
            "/reservations/1/check-in/",
            "/admin-dashboard/",
            "/admin-dashboard/spaces/",
            "/admin-dashboard/reservations/",
            "/admin-dashboard/maintenance/",
        ]
        for url in protected_urls:
            response = client.get(url)
            assert response.status_code in (302, 403), (
                f"Unexpected status {response.status_code} for {url}"
            )
            if response.status_code == 302:
                assert "/accounts/login/" in response.url


@pytest.mark.django_db
class TestAdminInterfaceFlow:
    """End-to-end tests for admin-facing web interface flows."""

    def test_admin_logs_in_sees_dashboard_navigates_to_spaces(self, client):
        """Admin logs in, sees dashboard with occupancy data, navigates to spaces."""
        space = Space.objects.create(
            name="Sala Admin Flow", capacity=5, location="Térreo", is_active=True
        )
        User.objects.create_user(username="adminflow", password="testpass123", is_staff=True)
        client.login(username="adminflow", password="testpass123")

        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["total_spaces"] == 1
        assert "space_cards" in response.context

        response = client.get("/admin-dashboard/spaces/")
        assert response.status_code == 200
        assert space in list(response.context["spaces"])

    def test_admin_creates_space_with_attributes_appears_in_user_search(self, client):
        """Admin creates space with attributes; it appears in user-facing search."""
        User.objects.create_user(username="admincreate", password="testpass123", is_staff=True)
        User.objects.create_user(username="regularsearch", password="testpass123")
        attr = Attribute.objects.create(name="Webcam")

        client.login(username="admincreate", password="testpass123")
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Sala Nova Admin",
                "description": "",
                "capacity": 10,
                "location": "Bloco D",
                "is_active": "on",
                "attributes": [str(attr.pk)],
            },
        )
        assert response.status_code == 302
        space = Space.objects.get(name="Sala Nova Admin")
        attr_names = set(space.space_attributes.values_list("attribute__name", flat=True))
        assert attr_names == {"Webcam"}

        # Regular user searches and finds the new space
        client.login(username="regularsearch", password="testpass123")
        response = client.get("/spaces/", {"attributes": "Webcam"})
        assert response.status_code == 200
        assert space in list(response.context["spaces"])

    def test_admin_cancels_user_reservation(self, client):
        """Admin cancels any user's reservation and status changes to cancelled."""
        space = Space.objects.create(
            name="Sala Admin Cancel", capacity=5, location="1º andar", is_active=True
        )
        User.objects.create_user(username="admincancel", password="testpass123", is_staff=True)
        user = User.objects.create_user(username="reservationowner", password="testpass123")

        now = timezone.now()
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )

        client.login(username="admincancel", password="testpass123")
        response = client.post(f"/admin-dashboard/reservations/{reservation.pk}/cancel/")
        assert response.status_code == 200

        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

    def test_admin_creates_maintenance_block_blocks_user_reservation(self, client):
        """Admin creates maintenance block; user cannot reserve that slot."""
        space = Space.objects.create(
            name="Sala Admin Maint", capacity=5, location="2º andar", is_active=True
        )
        User.objects.create_user(username="adminmaint", password="testpass123", is_staff=True)
        User.objects.create_user(username="regularuser", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)

        client.login(username="adminmaint", password="testpass123")
        response = client.post(
            "/admin-dashboard/maintenance/new/",
            {
                "space": str(space.pk),
                # datetime-local é hora de parede local, não UTC
                "start_time": timezone.localtime(start).strftime("%Y-%m-%dT%H:%M"),
                "end_time": timezone.localtime(end).strftime("%Y-%m-%dT%H:%M"),
                "reason": "Manutenção preventiva",
            },
        )
        assert response.status_code == 302
        assert MaintenanceBlock.objects.filter(reason="Manutenção preventiva").exists()

        # User tries to reserve the same slot and is rejected
        client.login(username="regularuser", password="testpass123")
        response = client.post(
            "/api/v1/reservations/",
            {
                "space": space.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_non_staff_gets_403_on_all_admin_dashboard_routes(self, client):
        """Non-staff users get 403 on all admin-dashboard routes."""
        User.objects.create_user(username="nonstaff", password="testpass123")
        client.login(username="nonstaff", password="testpass123")

        admin_urls = [
            "/admin-dashboard/",
            "/admin-dashboard/spaces/",
            "/admin-dashboard/spaces/new/",
            "/admin-dashboard/reservations/",
            "/admin-dashboard/maintenance/",
            "/admin-dashboard/maintenance/new/",
        ]
        for url in admin_urls:
            response = client.get(url)
            assert response.status_code == 403, (
                f"Expected 403 for {url}, got {response.status_code}"
            )


class AcabamentoTestCase(TestCase):
    """The finishing touches that no feature test would ever notice."""

    def test_base_template_declara_o_icone_da_aba(self):
        """Sem isto o navegador pede /favicon.ico e registra 404 a cada visita."""
        from django.template.loader import render_to_string

        html = render_to_string("base.html", {})
        assert 'rel="icon"' in html
        assert "logo.png" in html

    def test_form_control_existe_no_css(self):
        """A classe é usada em dezesseis templates e vinha do DaisyUI 4.

        Funcionava por acidente — os controles são ``w-full`` e ocupavam a linha
        inteira. Bastava um ``max-w`` num campo para o rótulo colar ao lado.
        """
        from pathlib import Path

        from django.conf import settings

        fonte = Path(settings.BASE_DIR) / "assets" / "css" / "source.css"
        assert ".form-control {" in fonte.read_text(encoding="utf-8")

    def test_classes_usadas_nos_templates_existem_no_css(self):
        """Uma classe de componente sem definição é estilo que ninguém vê faltar."""
        import re
        from pathlib import Path

        from django.conf import settings

        base = Path(settings.BASE_DIR)
        fonte = (base / "assets" / "css" / "source.css").read_text(encoding="utf-8")
        # Só as classes próprias desta interface: as do Tailwind e do DaisyUI
        # são geradas na compilação e não estariam aqui.
        proprias = {
            "surface",
            "notice",
            "sidebar-link",
            "nav-link",
            "step-marker",
            "step-label",
            "selectable-card",
            "avatar-initials",
            "brand-font",
            "brand-logo",
            "form-control",
        }
        usadas = set()
        for template in (base / "templates").rglob("*.html"):
            for atributo in re.findall(r'class="([^"]*)"', template.read_text(encoding="utf-8")):
                usadas |= set(atributo.split()) & proprias
        ausentes = {classe for classe in usadas if f".{classe} {{" not in fonte}
        assert not ausentes, f"classes usadas sem definição no CSS: {sorted(ausentes)}"
