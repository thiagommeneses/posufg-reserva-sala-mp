"""WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()


def _servir_midia(app):
    """Wrap the WSGI app so WhiteNoise also serves user-uploaded media.

    O middleware do WhiteNoise cuida dos estáticos coletados; a mídia é outro
    diretório, com outro ciclo de vida — arquivos aparecem depois que o processo
    subiu, quando um administrador envia uma foto. Por isso ``autorefresh``:
    sem ele o WhiteNoise mapeia o diretório uma única vez na inicialização e uma
    foto enviada em seguida devolveria 404 até o próximo deploy.

    O custo é um ``stat`` por requisição de mídia, aceitável na escala deste
    sistema — dezenas de imagens, servidas do cache do navegador na maior parte
    das vezes. É o que dispensa um nginx só para servir fotos de sala.

    As fotos são de salas de reunião, sem restrição de acesso. Se algum dia
    entrar arquivo restrito, este atalho deixa de servir e a mídia passa a
    precisar de uma view com verificação de permissão.

    Args:
        app: A aplicação WSGI do Django.

    Returns:
        A aplicação, embrulhada quando há mídia a servir.
    """
    from django.conf import settings

    if settings.DEBUG:
        # Em desenvolvimento quem serve /media/ é o próprio urls.py.
        return app

    from whitenoise import WhiteNoise

    return WhiteNoise(
        app,
        root=settings.MEDIA_ROOT,
        prefix=settings.MEDIA_URL,
        autorefresh=True,
    )


application = _servir_midia(application)
