"""Serializer fields shared across apps.

Existe um detalhe do DRF que morde ao trocar ``TIME_ZONE``: ``DateTimeField``
representa a saída no fuso ativo. Com ``TIME_ZONE = "America/Sao_Paulo"``, um
instante que sempre foi serializado como ``2026-08-25T13:00:00Z`` passaria a sair
como ``2026-08-25T10:00:00-03:00`` — mesmo instante, representação diferente, e
uma quebra silenciosa do contrato público documentado da API.

Este módulo mantém a API em UTC com sufixo ``Z``, independentemente do fuso de
exibição usado pela interface web.
"""

import datetime

from rest_framework import serializers


class UTCDateTimeField(serializers.DateTimeField):
    """A ``DateTimeField`` that always represents instants in UTC.

    O DRF consulta ``self.timezone`` em ``enforce_timezone``; fixá-lo em UTC faz
    o ``isoformat()`` terminar em ``+00:00``, que o próprio DRF converte para
    ``Z``. A entrada continua aceitando qualquer offset.
    """

    timezone = datetime.UTC


#: Mapeamento pronto para ``ModelSerializer.serializer_field_mapping``, para que
#: todo ``DateTimeField`` de modelo saia em UTC sem precisar ser declarado campo
#: a campo em cada serializer.
def utc_datetime_field_mapping(base_mapping):
    """Return a copy of ``base_mapping`` with datetimes mapped to UTC output.

    Args:
        base_mapping: O ``serializer_field_mapping`` herdado do ModelSerializer.

    Returns:
        dict: Cópia do mapa com ``models.DateTimeField`` apontando para
        :class:`UTCDateTimeField`.
    """
    from django.db import models

    mapping = dict(base_mapping)
    mapping[models.DateTimeField] = UTCDateTimeField
    return mapping
