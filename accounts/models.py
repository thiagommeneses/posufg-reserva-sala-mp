"""Models for the accounts app."""

from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra information about a user that the reservation flow needs.

    O pacote V2 é direto: "não pedir unidade, e-mail ou nome se o sistema puder
    obter do usuário/perfil". O passo 3 da reserva não deve ter campo de
    organizador — o organizador é quem está logado. O que falta no ``User`` do
    Django é a **lotação**, e é para isso que esta tabela existe.

    Os dois campos são texto livre e opcionais de propósito. A estrutura
    organizacional do MPGO não está neste sistema, e transformar lotação num
    catálogo exigiria mantê-lo sincronizado com algo que ninguém aqui controla.
    Texto livre é honesto sobre o que se sabe.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Nome completo",
        help_text="Como seu nome aparece nas reservas. Deixe em branco para usar o usuário.",
    )
    department = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Lotação",
        help_text="Setor, promotoria ou unidade. Aparece no resumo da reserva.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Profile."""

        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        """Return the display name."""
        return self.nome_de_exibicao

    @property
    def nome_de_exibicao(self):
        """Return the best name available for this user.

        Returns:
            str: O nome completo do perfil, o nome do ``User``, ou o usuário.
        """
        return self.full_name or self.user.get_full_name() or self.user.username

    @classmethod
    def carregar(cls, user):
        """Return this user's profile, creating an empty one if needed.

        Criar sob demanda evita um sinal em ``post_save`` de ``User``: quem
        precisa do perfil pede, e quem nunca precisa não gera linha. Também
        dispensa uma migration de dados para os usuários que já existem.

        Args:
            user: O usuário.

        Returns:
            Profile: O perfil correspondente.
        """
        perfil, _ = cls.objects.get_or_create(user=user)
        return perfil


def nome_de_exibicao(user):
    """Return the best display name for a user, with or without a profile.

    Existe para os templates: ``user.profile`` levanta ``RelatedObjectDoesNotExist``
    para quem ainda não tem perfil, e um template não tem como tratar isso.

    Args:
        user: O usuário.

    Returns:
        str: Nome completo, nome do ``User`` ou o nome de usuário.
    """
    perfil = getattr(user, "profile", None)
    if perfil is not None:
        return perfil.nome_de_exibicao
    return user.get_full_name() or user.username
