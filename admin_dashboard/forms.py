"""Forms for the admin dashboard app."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from core.models import HelpArticle
from reservations.models import BookingPolicy, MaintenanceBlock
from reservations.validators import validate_maintenance_slot
from services.models import ServiceType
from spaces.models import Attribute, Space, SpaceAttribute, SpaceType
from spaces.validators import ICONES_DISPONIVEIS

USER_FIELD_WIDGETS = {
    "username": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
    "is_staff": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
    "is_active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
}


class AdminUserCreateForm(forms.ModelForm):
    """Form for creating a user from the admin dashboard."""

    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"}),
    )
    password2 = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"}),
    )

    class Meta:
        """Meta options for AdminUserCreateForm."""

        model = User
        fields = ["username", "email", "is_staff", "is_active"]
        widgets = USER_FIELD_WIDGETS

    def clean_password2(self):
        """Validate that password1 and password2 match and meet strength rules."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("As senhas não coincidem.")
        validate_password(password2)
        return password2

    def save(self, commit=True):
        """Save the user with the provided password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class AdminUserUpdateForm(forms.ModelForm):
    """Form for editing a user from the admin dashboard, with optional password reset."""

    password1 = forms.CharField(
        label="Nova senha",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Deixe em branco para manter a senha atual",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmar nova senha",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"}),
    )

    class Meta:
        """Meta options for AdminUserUpdateForm."""

        model = User
        fields = ["username", "email", "is_staff", "is_active"]
        widgets = USER_FIELD_WIDGETS

    def clean_password2(self):
        """Validate the new password, if one was provided."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 or password2:
            if password1 != password2:
                raise ValidationError("As senhas não coincidem.")
            validate_password(password2)
        return password2

    def save(self, commit=True):
        """Save the user, updating the password only if a new one was provided."""
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


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
        fields = [
            "name",
            "description",
            "space_type",
            "capacity",
            "location",
            "cover_image",
            "is_active",
            "attributes",
        ]
        widgets = {
            "space_type": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "cover_image": forms.ClearableFileInput(
                attrs={"class": "file-input w-full", "accept": "image/jpeg,image/png,image/webp"}
            ),
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "capacity": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "location": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
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
            validate_maintenance_slot(space, start_time, end_time)

        return cleaned_data


class SpaceTypeForm(forms.ModelForm):
    """Form for creating and updating space types."""

    class Meta:
        """Meta options for SpaceTypeForm."""

        model = SpaceType
        fields = ["name", "slug", "icon_name", "sort_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "slug": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "icon_name": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "sort_order": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
        }

    def __init__(self, *args, **kwargs):
        """Offer the icon catalog as a select, instead of free text.

        Digitar o nome do ícone à mão erra fácil, e o erro só aparece na tela.
        Um select com o catálogo torna o campo impossível de preencher errado.
        """
        super().__init__(*args, **kwargs)
        opcoes = [("", "Sem ícone")] + [(nome, nome) for nome in sorted(ICONES_DISPONIVEIS)]
        self.fields["icon_name"].widget.choices = opcoes
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Deixe em branco para gerar a partir do nome."

    def clean_slug(self):
        """Derive the slug from the name when it is left blank."""
        slug = self.cleaned_data.get("slug")
        if slug:
            return slug
        return slugify(self.cleaned_data.get("name", ""))


class BookingPolicyForm(forms.ModelForm):
    """Form for the single booking policy row.

    Os sete dias da semana são um conceito só, não sete interruptores
    independentes, e por isso a tela precisa desenhá-los juntos. Quem sabe
    quais campos são esses é este formulário — via :attr:`campos_de_dia` —, e
    não o template: o template continua sem conhecer nome de campo nenhum,
    que é o que o mantém correto quando a política ganha um parâmetro novo.
    """

    @property
    def campos_de_dia(self):
        """Return the bound fields of the weekday switches, Monday first."""
        return [self[nome] for nome in BookingPolicy.CAMPOS_DE_DIA]

    @property
    def campos_gerais(self):
        """Return every other bound field, in the order declared in Meta."""
        dias = set(BookingPolicy.CAMPOS_DE_DIA)
        return [campo for campo in self if campo.name not in dias]

    class Meta:
        """Meta options for BookingPolicyForm."""

        model = BookingPolicy
        fields = [
            "opening_time",
            "closing_time",
            "slot_minutes",
            "min_duration_minutes",
            "max_duration_minutes",
            "horizon_days",
            "few_slots_threshold",
            "opens_monday",
            "opens_tuesday",
            "opens_wednesday",
            "opens_thursday",
            "opens_friday",
            "opens_saturday",
            "opens_sunday",
            # A ordem é a de leitura: o interruptor primeiro, o número que
            # ele usa logo abaixo. Ao contrário, a tolerância aparecia antes
            # da regra que lhe dá sentido.
            "enforce_window",
            "release_no_shows",
            "no_show_threshold_minutes",
        ]
        widgets = {
            "opening_time": forms.TimeInput(
                format="%H:%M", attrs={"type": "time", "class": "input input-bordered w-full"}
            ),
            "closing_time": forms.TimeInput(
                format="%H:%M", attrs={"type": "time", "class": "input input-bordered w-full"}
            ),
            "slot_minutes": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "min_duration_minutes": forms.NumberInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "max_duration_minutes": forms.NumberInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "horizon_days": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "few_slots_threshold": forms.NumberInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "no_show_threshold_minutes": forms.NumberInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "enforce_window": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "release_no_shows": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            **{
                nome: forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"})
                for nome in BookingPolicy.CAMPOS_DE_DIA
            },
        }


class AttributeForm(forms.ModelForm):
    """Form for creating and updating equipment attributes."""

    class Meta:
        """Meta options for AttributeForm."""

        model = Attribute
        fields = ["name", "category", "icon_name", "is_featured", "sort_order"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "category": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "icon_name": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "sort_order": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
        }

    def __init__(self, *args, **kwargs):
        """Offer the icon catalog as a select, as in SpaceTypeForm."""
        super().__init__(*args, **kwargs)
        opcoes = [("", "Sem ícone")] + [(nome, nome) for nome in sorted(ICONES_DISPONIVEIS)]
        self.fields["icon_name"].widget.choices = opcoes


class ServiceTypeForm(forms.ModelForm):
    """Form for creating and updating service types."""

    class Meta:
        """Meta options for ServiceTypeForm."""

        model = ServiceType
        fields = [
            "name",
            "slug",
            "category",
            "description",
            "icon_name",
            "spaces",
            "min_lead_time_hours",
            "requires_notes",
            "is_active",
            "sort_order",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "slug": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "category": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 2}
            ),
            "icon_name": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "spaces": forms.CheckboxSelectMultiple(),
            "min_lead_time_hours": forms.NumberInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "requires_notes": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "sort_order": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
        }

    def __init__(self, *args, **kwargs):
        """Offer the icon catalog as a select and derive the slug from the name."""
        super().__init__(*args, **kwargs)
        opcoes = [("", "Sem ícone")] + [(nome, nome) for nome in sorted(ICONES_DISPONIVEIS)]
        self.fields["icon_name"].widget.choices = opcoes
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Deixe em branco para gerar a partir do nome."
        # Só espaços ativos: vincular um serviço a um espaço desativado criaria
        # uma oferta que nunca aparece — e que ninguém entenderia ao revisar.
        self.fields["spaces"].queryset = Space.objects.filter(is_active=True).order_by("name")

    def clean_slug(self):
        """Derive the slug from the name when it is left blank."""
        slug = self.cleaned_data.get("slug")
        if slug:
            return slug
        return slugify(self.cleaned_data.get("name", ""))


class HelpArticleForm(forms.ModelForm):
    """Form for the institutional help blocks.

    O ``slug`` não está aqui de propósito: ele é a âncora da seção na tela de
    Ajuda e o modelo o deriva do título. Pedi-lo ao administrador seria expor um
    detalhe de implementação numa tela cujo assunto é escrever texto.
    """

    class Meta:
        """Meta options for HelpArticleForm."""

        model = HelpArticle
        fields = ["title", "body", "sort_order", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "body": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 10}
            ),
            "sort_order": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "is_published": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
        }

    def clean_body(self):
        """Reject a body that is only whitespace.

        ``TextField`` obrigatório já barra o vazio, mas não barra um campo com
        três quebras de linha — que publicaria um bloco com título e nenhum
        parágrafo na tela de Ajuda.
        """
        body = self.cleaned_data.get("body", "")
        if not body.strip():
            raise ValidationError("Escreva o texto do bloco.")
        return body
