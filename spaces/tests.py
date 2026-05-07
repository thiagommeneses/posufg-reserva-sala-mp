"""Tests for the spaces app models."""

import pytest
from django.db.utils import IntegrityError

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
