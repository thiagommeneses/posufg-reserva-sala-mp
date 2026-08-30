"""Signals that keep the media directory free of orphan files.

O Django não apaga arquivo nenhum sozinho: excluir um ``Space`` ou trocar a foto
deixa o arquivo anterior no storage para sempre. Em um volume que entra na
rotina de backup, isso vira crescimento silencioso.

Os dois handlers abaixo apagam apenas arquivos que deixaram de ser referenciados
por qualquer registro — nunca um arquivo ainda em uso.
"""

import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from spaces.models import Space

logger = logging.getLogger(__name__)


def _apagar_arquivo(arquivo):
    """Delete a stored file, ignoring the case where it is already gone.

    Args:
        arquivo: O ``FieldFile`` a remover.
    """
    if not arquivo:
        return
    try:
        arquivo.storage.delete(arquivo.name)
    except OSError:  # pragma: no cover - depende do storage
        logger.warning("Não foi possível remover o arquivo de mídia %s", arquivo.name)


@receiver(pre_save, sender=Space)
def remover_capa_substituida(sender, instance, **kwargs):
    """Delete the previous cover image when a space gets a new one.

    Args:
        sender: A classe ``Space``.
        instance: A instância prestes a ser salva.
        **kwargs: Demais argumentos do sinal.
    """
    if not instance.pk:
        return

    anterior = Space.objects.filter(pk=instance.pk).values_list("cover_image", flat=True).first()
    if not anterior:
        return

    # O nome novo só é conhecido depois do processamento no save(); comparar os
    # nomes evita apagar o arquivo quando o campo não mudou.
    nome_novo = instance.cover_image.name if instance.cover_image else None
    if anterior != nome_novo:
        _apagar_arquivo(Space(cover_image=anterior).cover_image)


@receiver(post_delete, sender=Space)
def remover_capa_do_espaco_excluido(sender, instance, **kwargs):
    """Delete the cover image of a space that no longer exists.

    Args:
        sender: A classe ``Space``.
        instance: A instância recém-excluída.
        **kwargs: Demais argumentos do sinal.
    """
    _apagar_arquivo(instance.cover_image)
