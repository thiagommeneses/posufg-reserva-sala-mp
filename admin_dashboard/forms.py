"""Forms for the admin dashboard app."""

from django import forms

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
