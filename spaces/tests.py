"""Tests for the spaces app models and API."""

from datetime import datetime, time
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from ai_assistant.exceptions import AIServiceError
from reservations.models import MaintenanceBlock, Reservation, ReservationStatus

from .models import Attribute, Space, SpaceAttribute


@pytest.mark.django_db
class TestSpaceModel:
    """Tests for the Space model."""

    def test_create_space(self):
        """Creating a space with valid fields should succeed."""
        space = Space.objects.create(
            name="Conference Room A",
            description="A large conference room",
            capacity=20,
            location="Building 1, Floor 2",
            is_active=True,
        )
        assert space.name == "Conference Room A"
        assert space.description == "A large conference room"
        assert space.capacity == 20
        assert space.location == "Building 1, Floor 2"
        assert space.is_active is True
        assert space.created_at is not None
        assert space.updated_at is not None

    def test_space_str(self):
        """Space __str__ should return the name."""
        space = Space.objects.create(
            name="Meeting Room B",
            capacity=10,
            location="Building 2",
        )
        assert str(space) == "Meeting Room B"

    def test_space_ordering(self):
        """Spaces should be ordered by name."""
        Space.objects.create(name="Zebra Room", capacity=5, location="Z")
        Space.objects.create(name="Alpha Room", capacity=5, location="A")
        spaces = list(Space.objects.all())
        assert spaces[0].name == "Alpha Room"
        assert spaces[1].name == "Zebra Room"

    def test_is_active_default(self):
        """is_active should default to True."""
        space = Space.objects.create(name="Test Room", capacity=5, location="T")
        assert space.is_active is True

    def test_description_optional(self):
        """Description should be optional."""
        space = Space.objects.create(name="No Desc", capacity=5, location="T")
        assert space.description is None


@pytest.mark.django_db
class TestAttributeModel:
    """Tests for the Attribute model."""

    def test_create_attribute(self):
        """Creating an attribute with a name should succeed."""
        attr = Attribute.objects.create(name="TV")
        assert attr.name == "TV"

    def test_attribute_str(self):
        """Attribute __str__ should return the name."""
        attr = Attribute.objects.create(name="Projector")
        assert str(attr) == "Projector"

    def test_attribute_name_unique(self):
        """Attribute names must be unique."""
        Attribute.objects.create(name="Whiteboard")
        with pytest.raises(IntegrityError):
            Attribute.objects.create(name="Whiteboard")

    def test_attribute_ordering(self):
        """Attributes should be ordered by name."""
        Attribute.objects.create(name="Zebra")
        Attribute.objects.create(name="Alpha")
        attrs = list(Attribute.objects.all())
        assert attrs[0].name == "Alpha"
        assert attrs[1].name == "Zebra"


@pytest.mark.django_db
class TestSpaceAttributeModel:
    """Tests for the SpaceAttribute through model."""

    def test_create_space_attribute(self):
        """Linking a space and attribute should succeed."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        space_attr = SpaceAttribute.objects.create(space=space, attribute=attr)
        assert space_attr.space == space
        assert space_attr.attribute == attr
        assert str(space_attr) == "Room — TV"

    def test_space_attribute_unique(self):
        """Duplicate space-attribute pairs should be rejected."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        with pytest.raises(IntegrityError):
            SpaceAttribute.objects.create(space=space, attribute=attr)

    def test_space_related_name(self):
        """Space should access linked attributes via space_attributes."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        assert space.space_attributes.count() == 1
        assert space.space_attributes.first().attribute == attr

    def test_attribute_related_name(self):
        """Attribute should access linked spaces via space_attributes."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        assert attr.space_attributes.count() == 1
        assert attr.space_attributes.first().space == space


@pytest.fixture
def api_client():
    """Provide a DRF API test client."""
    return APIClient()


@pytest.fixture
def regular_user(db):
    """Create a regular (non-admin) test user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="regularpass123",  # noqa: S106
    )


@pytest.fixture
def admin_user(db):
    """Create an admin test user."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",  # noqa: S106
    )


@pytest.fixture
def space_with_tv(db):
    """Create a space linked to a 'TV' attribute."""
    space = Space.objects.create(
        name="Room with TV",
        capacity=10,
        location="Building A",
    )
    attr = Attribute.objects.create(name="TV")
    SpaceAttribute.objects.create(space=space, attribute=attr)
    return space


@pytest.fixture
def small_space(db):
    """Create a small space with no attributes."""
    return Space.objects.create(
        name="Small Room",
        capacity=4,
        location="Building B",
    )


class TestSpaceApiList:
    """Tests for listing spaces via the API."""

    def test_list_spaces_authenticated(self, api_client, regular_user, space_with_tv):
        """Authenticated users should receive a list of spaces with attributes."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/v1/spaces/")
        assert response.status_code == 200
        assert len(response.data) >= 1
        space_data = next(s for s in response.data if s["id"] == space_with_tv.id)
        assert "TV" in space_data["attributes"]

    def test_list_spaces_unauthenticated(self, api_client):
        """Unauthenticated requests should be rejected."""
        response = api_client.get("/api/v1/spaces/")
        assert response.status_code in (401, 403)

    def test_filter_by_min_capacity(self, api_client, regular_user, space_with_tv, small_space):
        """Filtering by min_capacity should exclude smaller spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/v1/spaces/?min_capacity=6")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names
        assert "Small Room" not in names

    def test_filter_by_max_capacity(self, api_client, regular_user, space_with_tv, small_space):
        """Filtering by max_capacity should exclude larger spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/v1/spaces/?max_capacity=4")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Small Room" in names
        assert "Room with TV" not in names

    def test_filter_by_attributes(self, api_client, regular_user, space_with_tv, small_space):
        """Filtering by attributes should return only matching spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/v1/spaces/?attributes=TV")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names
        assert "Small Room" not in names

    def test_filter_by_location_case_insensitive(self, api_client, regular_user, space_with_tv):
        """Location filter should be case-insensitive."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/v1/spaces/?location=building a")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names


class TestSpaceApiRetrieve:
    """Tests for retrieving a single space via the API."""

    def test_retrieve_space_detail(self, api_client, regular_user, space_with_tv):
        """Authenticated users should be able to retrieve space details."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get(f"/api/v1/spaces/{space_with_tv.id}/")
        assert response.status_code == 200
        assert response.data["name"] == "Room with TV"
        assert "TV" in response.data["attributes"]


class TestSpaceApiCreate:
    """Tests for creating spaces via the API."""

    def test_admin_can_create_space(self, api_client, admin_user):
        """Admin users should be able to create new spaces."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/spaces/",
            {
                "name": "New Room",
                "capacity": 20,
                "location": "Building C",
            },
        )
        assert response.status_code == 201
        assert response.data["name"] == "New Room"
        assert Space.objects.filter(name="New Room").exists()

    def test_non_admin_cannot_create_space(self, api_client, regular_user):
        """Non-admin users should be forbidden from creating spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.post(
            "/api/v1/spaces/",
            {
                "name": "New Room",
                "capacity": 20,
                "location": "Building C",
            },
        )
        assert response.status_code == 403


class TestSpaceAvailability:
    """Tests for the space availability endpoint."""

    def test_availability_reflects_reservations(self, api_client, regular_user, space_with_tv):
        """Confirmed reservations should appear as occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(10, 0)))
        end = timezone.make_aware(datetime.combine(today, time(12, 0)))
        Reservation.objects.create(
            space=space_with_tv,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.get(
            f"/api/v1/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        assert response.data["date"] == today.isoformat()
        occupied = response.data["occupied"]
        assert len(occupied) == 1
        assert occupied[0]["type"] == "reservation"
        free = response.data["free"]
        assert len(free) == 2  # midnight-10am and 12pm-midnight

    def test_availability_reflects_maintenance_blocks(
        self,
        api_client,
        regular_user,
        space_with_tv,
    ):
        """Maintenance blocks should appear as occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(14, 0)))
        end = timezone.make_aware(datetime.combine(today, time(15, 0)))
        MaintenanceBlock.objects.create(
            space=space_with_tv,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=regular_user,
        )
        response = api_client.get(
            f"/api/v1/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        occupied = response.data["occupied"]
        assert len(occupied) == 1
        assert occupied[0]["type"] == "maintenance"

    def test_cancelled_reservation_does_not_block(self, api_client, regular_user, space_with_tv):
        """Cancelled reservations should not appear in occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(10, 0)))
        end = timezone.make_aware(datetime.combine(today, time(12, 0)))
        Reservation.objects.create(
            space=space_with_tv,
            user=regular_user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CANCELLED,
        )
        response = api_client.get(
            f"/api/v1/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        assert response.data["occupied"] == []
        assert len(response.data["free"]) == 1  # entire day free


@pytest.mark.django_db
class TestSpaceDetailView:
    """Tests for the user-facing space detail view."""

    def test_page_renders_with_space_info_and_availability(
        self, client, regular_user, space_with_tv
    ):
        """Page should render with space info and availability data."""
        client.force_login(regular_user)
        response = client.get(f"/spaces/{space_with_tv.id}/")
        assert response.status_code == 200
        assert "spaces/space_detail.html" in [t.name for t in response.templates]
        assert response.context["space"] == space_with_tv
        # Desde a Fase 4 a tela recebe os horários já fatiados no incremento da
        # política, em vez dos intervalos contínuos da API.
        assert "slots" in response.context
        assert "selected_date" in response.context

    def test_htmx_request_returns_partial(self, client, regular_user, space_with_tv):
        """HTMX request should return partial template with availability."""
        client.force_login(regular_user)
        today = timezone.localdate().isoformat()
        response = client.get(f"/spaces/{space_with_tv.id}/?date={today}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "spaces/_availability.html" in [t.name for t in response.templates]
        assert "base.html" not in [t.name for t in response.templates]

    def test_unauthenticated_user_redirected_to_login(self, client, space_with_tv):
        """Unauthenticated users should be redirected to login."""
        response = client.get(f"/spaces/{space_with_tv.id}/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_default_date_is_today(self, client, regular_user, space_with_tv):
        """Default selected_date should be today when no date param provided.

        "Hoje" é o de quem usa a tela, e não o do relógio do servidor:
        ``date.today()`` devolve o dia em UTC e, das 21h à meia-noite em
        Goiás, já é o dia seguinte.
        """
        client.force_login(regular_user)
        response = client.get(f"/spaces/{space_with_tv.id}/")
        assert response.status_code == 200
        assert response.context["selected_date"] == timezone.localdate()

    def test_custom_date_from_query_param(self, client, regular_user, space_with_tv):
        """Selected date should come from query parameter."""
        from datetime import date

        client.force_login(regular_user)
        custom_date = "2025-12-25"
        response = client.get(f"/spaces/{space_with_tv.id}/?date={custom_date}")
        assert response.status_code == 200
        assert response.context["selected_date"] == date(2025, 12, 25)

    def test_invalid_date_defaults_to_today(self, client, regular_user, space_with_tv):
        """Invalid date format should default to today."""
        client.force_login(regular_user)
        response = client.get(f"/spaces/{space_with_tv.id}/?date=invalid-date")
        assert response.status_code == 200
        assert response.context["selected_date"] == timezone.localdate()

    def test_availability_reflects_reservations(self, client, regular_user, space_with_tv):
        """Availability should show occupied slots from reservations."""
        from datetime import datetime, time

        from django.utils import timezone

        from reservations.models import BookingPolicy

        # O teste é sobre fatiamento de horário, não sobre dia da semana: sem
        # abrir o fim de semana ele passaria de segunda a sexta e falharia aos
        # sábados, por um motivo que não tem relação com o que ele afirma.
        politica = BookingPolicy.carregar()
        politica.opens_saturday = True
        politica.opens_sunday = True
        politica.save(update_fields=["opens_saturday", "opens_sunday"])

        client.force_login(regular_user)
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time(10, 0)))
        end = timezone.make_aware(datetime.combine(today, time(12, 0)))
        Reservation.objects.create(
            space=space_with_tv,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = client.get(f"/spaces/{space_with_tv.id}/")
        assert response.status_code == 200
        slots = response.context["slots"]
        ocupados = [slot for slot in slots if slot["situacao"] == "reservado"]
        # Das 10h às 12h, em pedaços de 30 minutos, são quatro.
        assert len(ocupados) == 4
        assert ocupados[0]["inicio"] == start
        assert all(not slot["disponivel"] for slot in ocupados)

    def test_inactive_space_returns_404(self, client, regular_user):
        """Inactive spaces should return 404."""
        inactive_space = Space.objects.create(
            name="Inactive Room",
            capacity=10,
            location="Test",
            is_active=False,
        )
        client.force_login(regular_user)
        response = client.get(f"/spaces/{inactive_space.id}/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestSpaceListView:
    """Tests for the user-facing space list view."""

    def test_authenticated_user_gets_200(self, client, regular_user):
        """Authenticated users should see the space list page."""
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        assert "spaces/space_list.html" in [t.name for t in response.templates]

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login."""
        response = client.get("/spaces/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_filter_by_min_capacity(self, client, regular_user, space_with_tv, small_space):
        """Filtering by min_capacity should return only matching spaces."""
        client.force_login(regular_user)
        response = client.get("/spaces/?min_capacity=6")
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert space_with_tv in spaces
        assert small_space not in spaces

    def test_filter_by_max_capacity(self, client, regular_user, space_with_tv, small_space):
        """Filtering by max_capacity should exclude larger spaces."""
        client.force_login(regular_user)
        response = client.get("/spaces/?max_capacity=4")
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert small_space in spaces
        assert space_with_tv not in spaces
        assert response.context["max_capacity"] == "4"

    def test_filter_by_location(self, client, regular_user, space_with_tv, small_space):
        """Filtering by location should return only matching spaces."""
        client.force_login(regular_user)
        response = client.get("/spaces/?location=building+a")
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert space_with_tv in spaces
        assert small_space not in spaces

    def test_filter_by_attributes(self, client, regular_user, space_with_tv, small_space):
        """Filtering by attributes should return only matching spaces."""
        client.force_login(regular_user)
        response = client.get("/spaces/?attributes=TV")
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert space_with_tv in spaces
        assert small_space not in spaces

    def test_htmx_request_returns_partial(self, client, regular_user, space_with_tv):
        """HTMX requests should return the partial template without base layout."""
        client.force_login(regular_user)
        response = client.get("/spaces/", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "spaces/_space_list_results.html" in [t.name for t in response.templates]
        assert "base.html" not in [t.name for t in response.templates]

    def test_context_includes_attributes(self, client, regular_user):
        """Context should include all attributes for the filter checkboxes."""
        attr1 = Attribute.objects.create(name="TV")
        attr2 = Attribute.objects.create(name="Projector")
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        assert "attributes" in response.context
        attributes = list(response.context["attributes"])
        assert attr1 in attributes
        assert attr2 in attributes

    def test_context_includes_selected_filters(self, client, regular_user):
        """Context should include selected filter values."""
        client.force_login(regular_user)
        response = client.get("/spaces/?min_capacity=5&location=Building&attributes=TV")
        assert response.status_code == 200
        assert response.context["min_capacity"] == "5"
        assert response.context["location"] == "Building"
        assert response.context["selected_attributes"] == ["TV"]

    def test_inactive_spaces_excluded(self, client, regular_user):
        """Inactive spaces should not appear in the list."""
        Space.objects.create(
            name="Inactive Room",
            capacity=10,
            location="Test",
            is_active=False,
        )
        active_space = Space.objects.create(
            name="Active Room",
            capacity=10,
            location="Test",
            is_active=True,
        )
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        spaces = list(response.context["spaces"])
        assert active_space in spaces
        assert not any(s.name == "Inactive Room" for s in spaces)

    def test_filter_button_aligned_with_fields(self, client, regular_user):
        """The search button container should vertically align with the inputs."""
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        content = response.content.decode()
        # Desde a Fase 7 o rótulo é "Buscar": o formulário deixou de ser só de
        # filtros e passou a reunir data, pessoas e busca.
        assert 'class="form-control justify-start"' in content
        assert "Buscar" in content

    def test_filter_spinner_hidden_on_initial_load(self, client, regular_user):
        """Spinner must be an htmx-indicator, hidden by default via CSS (not inline style)."""
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="loading-indicator"' in content
        assert "htmx-indicator" in content
        assert 'style="display: none;"' not in content

    def test_filter_spinner_on_form_and_checkboxes(self, client, regular_user):
        """Form submit and checkbox changes should trigger the same loading indicator."""
        Attribute.objects.create(name="TV")
        Attribute.objects.create(name="Projetor")
        client.force_login(regular_user)
        response = client.get("/spaces/")
        assert response.status_code == 200
        content = response.content.decode()
        # The form should reference the indicator
        assert 'hx-indicator="#loading-indicator"' in content
        # Every attribute checkbox should also reference the same indicator
        attribute_checkbox_count = content.count('name="attributes"')
        assert attribute_checkbox_count > 0
        indicator_count = content.count('hx-indicator="#loading-indicator"')
        # Todo controle que dispara uma busca mostra o mesmo spinner: o
        # formulário, o campo de data (que busca ao mudar) e cada checkbox.
        assert indicator_count == attribute_checkbox_count + 2

    def test_multiple_attributes_are_all_applied(self, client, regular_user):
        """Two checked equipment boxes must both narrow the result (AND).

        Os checkboxes enviam um ``attributes`` por item marcado. Com
        ``request.GET.get`` só o último chegava ao filtro e os demais eram
        ignorados em silêncio.
        """
        tv = Attribute.objects.create(name="TV")
        projetor = Attribute.objects.create(name="Projetor")

        ambos = Space.objects.create(name="Sala Completa", capacity=10, location="Bloco A")
        SpaceAttribute.objects.create(space=ambos, attribute=tv)
        SpaceAttribute.objects.create(space=ambos, attribute=projetor)

        so_tv = Space.objects.create(name="Sala So TV", capacity=10, location="Bloco A")
        SpaceAttribute.objects.create(space=so_tv, attribute=tv)

        client.force_login(regular_user)
        response = client.get("/spaces/?attributes=TV&attributes=Projetor")
        assert response.status_code == 200

        nomes = {space.name for space in response.context["spaces"]}
        assert "Sala Completa" in nomes
        assert "Sala So TV" not in nomes
        assert response.context["selected_attributes"] == ["TV", "Projetor"]

    def test_comma_separated_attributes_still_work(self, client, regular_user):
        """The comma form (the API contract, and old bookmarks) keeps working."""
        tv = Attribute.objects.create(name="TV")
        projetor = Attribute.objects.create(name="Projetor")
        sala = Space.objects.create(name="Sala Completa", capacity=10, location="Bloco A")
        SpaceAttribute.objects.create(space=sala, attribute=tv)
        SpaceAttribute.objects.create(space=sala, attribute=projetor)

        client.force_login(regular_user)
        response = client.get("/spaces/?attributes=TV,Projetor")
        assert response.status_code == 200
        assert response.context["selected_attributes"] == ["TV", "Projetor"]
        assert {space.name for space in response.context["spaces"]} == {"Sala Completa"}

    def test_selected_attributes_never_match_by_substring(self, client, regular_user):
        """A selected attribute must not mark another whose name contains it."""
        Attribute.objects.create(name="TV")
        Attribute.objects.create(name="Videoconferencia")

        client.force_login(regular_user)
        response = client.get("/spaces/?attributes=Videoconferencia")
        assert response.status_code == 200
        assert response.context["selected_attributes"] == ["Videoconferencia"]
        assert "TV" not in response.context["selected_attributes"]


@pytest.mark.django_db
class TestSpaceListViewAISearch:
    """Tests for the natural-language AI search on the space list view."""

    @patch("spaces.views.extract_room_search_filters")
    def test_ai_query_filters_spaces(
        self, mock_extract, client, regular_user, space_with_tv, small_space
    ):
        """A successful AI query should filter spaces using the extracted filters."""
        mock_extract.return_value = {
            "min_capacity": 6,
            "max_capacity": None,
            "attributes": [],
            "location": None,
            "summary": "Sala para 6 ou mais pessoas.",
        }
        client.force_login(regular_user)
        response = client.get("/spaces/?ai_query=sala+para+6+pessoas")
        assert response.status_code == 200
        # Desde a Fase 8 o serviço também recebe o contexto temporal — sem ele,
        # o modelo não teria como resolver "amanhã".
        consulta, contexto = mock_extract.call_args.args
        assert consulta == "sala para 6 pessoas"
        assert contexto["hoje_date"] == timezone.localdate()
        spaces = list(response.context["spaces"])
        assert space_with_tv in spaces
        assert small_space not in spaces
        assert response.context["ai_summary"] == "Sala para 6 ou mais pessoas."

    @patch("spaces.views.extract_room_search_filters")
    def test_ai_query_filters_by_max_capacity(
        self, mock_extract, client, regular_user, space_with_tv, small_space
    ):
        """An AI upper-bound query should keep only rooms within max_capacity."""
        mock_extract.return_value = {
            "min_capacity": None,
            "max_capacity": 4,
            "attributes": [],
            "location": None,
            "summary": "Sala para até 4 pessoas.",
        }
        client.force_login(regular_user)
        response = client.get("/spaces/?ai_query=sala+para+ate+4+pessoas")
        assert response.status_code == 200
        spaces = list(response.context["spaces"])
        assert small_space in spaces
        assert space_with_tv not in spaces
        assert response.context["ai_summary"] == "Sala para até 4 pessoas."

    @patch("spaces.views.extract_room_search_filters")
    def test_ai_query_service_error_shows_message(self, mock_extract, client, regular_user):
        """When the AI service fails, the view should show an error, not crash."""
        mock_extract.side_effect = AIServiceError("Não foi possível consultar o serviço de IA.")
        client.force_login(regular_user)
        response = client.get("/spaces/?ai_query=sala+para+6+pessoas")
        assert response.status_code == 200
        assert response.context["ai_error"] == "Não foi possível consultar o serviço de IA."
        assert list(response.context["spaces"]) == []

    def test_blank_ai_query_falls_back_to_manual_filters(
        self, client, regular_user, space_with_tv, small_space
    ):
        """A blank ai_query should be ignored in favor of the manual filter fields."""
        client.force_login(regular_user)
        response = client.get("/spaces/?ai_query=&min_capacity=6")
        assert response.status_code == 200
        spaces = list(response.context["spaces"])
        assert space_with_tv in spaces
        assert small_space not in spaces
