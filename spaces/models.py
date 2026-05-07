"""Models for the spaces app."""

from django.db import models


class Space(models.Model):
    """A reservable space with capacity and location attributes."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField()
    location = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Space."""

        ordering = ["name"]

    def __str__(self):
        """Return the space name."""
        return self.name


class Attribute(models.Model):
    """An attribute that can be associated with a space (e.g., TV, projector)."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        """Meta options for Attribute."""

        ordering = ["name"]

    def __str__(self):
        """Return the attribute name."""
        return self.name


class SpaceAttribute(models.Model):
    """Many-to-many through model linking spaces and attributes."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="space_attributes")
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="space_attributes"
    )

    class Meta:
        """Meta options for SpaceAttribute."""

        constraints = [
            models.UniqueConstraint(
                fields=["space", "attribute"],
                name="unique_space_attribute",
            ),
        ]

    def __str__(self):
        """Return a human-readable description of the link."""
        return f"{self.space.name} — {self.attribute.name}"
