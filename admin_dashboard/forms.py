"""Forms for the admin dashboard app."""

from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Attribute, Space, SpaceAttribute


class SpaceForm(forms.ModelForm):
    """Form for creating and updating spaces with attribute management."""

    attributes = forms.ModelMultipleChoiceField(
        queryset=Attribute.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        """Meta options for SpaceForm."""

        model = Space
        fields = ["name", "description", "capacity", "location", "is_active", "attributes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "capacity": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "location": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form and pre-populate attributes for existing spaces."""
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["attributes"].initial = Attribute.objects.filter(
                space_attributes__space=self.instance
            ).values_list("pk", flat=True)

    def save(self, commit=True):
        """Save the space and update its attributes."""
        instance = super().save(commit=commit)
        self._save_attributes(instance)
        return instance

    def _save_attributes(self, instance):
        """Synchronize the SpaceAttribute through model with selected attributes."""
        selected_ids = {a.pk for a in self.cleaned_data.get("attributes", [])}
        current_ids = set(
            SpaceAttribute.objects.filter(space=instance).values_list("attribute_id", flat=True)
        )
        to_remove = current_ids - selected_ids
        to_add = selected_ids - current_ids
        if to_remove:
            SpaceAttribute.objects.filter(space=instance, attribute_id__in=to_remove).delete()
        for attr_id in to_add:
            SpaceAttribute.objects.create(space=instance, attribute_id=attr_id)


class MaintenanceBlockForm(forms.ModelForm):
    """Form for creating maintenance blocks with overlap validation."""

    class Meta:
        """Meta options for MaintenanceBlockForm."""

        model = MaintenanceBlock
        fields = ["space", "start_time", "end_time", "reason"]
        widgets = {
            "space": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "start_time": forms.DateTimeInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "type": "datetime-local",
                }
            ),
            "end_time": forms.DateTimeInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "type": "datetime-local",
                }
            ),
            "reason": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
        }

    def clean(self):
        """Validate that the maintenance block does not overlap with confirmed reservations."""
        cleaned_data = super().clean()
        space = cleaned_data.get("space")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if space and start_time and end_time:
            if end_time <= start_time:
                raise ValidationError("End time must be after start time.")

            overlapping_reservations = Reservation.objects.filter(
                space=space,
                status__in=[
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.CHECKED_IN,
                ],
            ).filter(
                models.Q(start_time__lt=end_time) & models.Q(end_time__gt=start_time),
            )
            if overlapping_reservations.exists():
                raise ValidationError(
                    "This maintenance block overlaps with an existing reservation.",
                )

        return cleaned_data
