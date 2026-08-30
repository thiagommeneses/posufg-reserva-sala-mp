"""Regression tests for the production deployment configuration.

Erro de configuração de deploy não aparece em desenvolvimento: só se manifesta no
servidor, geralmente como CSS que não carrega ou cookie de sessão trafegando em
texto claro. Estes testes prendem as decisões tomadas para que uma alteração
futura em ``settings.py`` não as desfaça sem que alguém perceba.
"""

import importlib
import os
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command


def _reload_settings(**env):
    """Import ``config.settings`` afresh with the given environment.

    ``settings.py`` decide storage e endurecimento de segurança no momento do
    import, a partir de variáveis de ambiente. Recarregar o módulo é a única
    forma de exercitar o caminho de produção sem subir outro processo.

    Args:
        **env: Variáveis de ambiente a aplicar durante o import.

    Returns:
        module: O módulo ``config.settings`` recarregado.
    """
    import config.settings as settings_module

    with mock.patch.dict(os.environ, env, clear=False):
        return importlib.reload(settings_module)


class TestStaticFilesConfiguration:
    """Static files need to survive the trip from the repository to production."""

    def test_static_root_is_defined(self):
        """``collectstatic`` needs a destination or the build step fails."""
        assert settings.STATIC_ROOT, "STATIC_ROOT é obrigatório para o collectstatic"

    def test_static_root_is_outside_the_source_directories(self):
        """STATIC_ROOT inside STATICFILES_DIRS makes collectstatic eat its own output."""
        static_root = Path(settings.STATIC_ROOT).resolve()
        for source in settings.STATICFILES_DIRS:
            source = Path(source).resolve()
            assert static_root != source
            assert source not in static_root.parents

    def test_whitenoise_sits_right_after_the_security_middleware(self):
        """WhiteNoise só funciona nessa posição — é o que a documentação exige."""
        middleware = list(settings.MIDDLEWARE)
        security = middleware.index("django.middleware.security.SecurityMiddleware")
        assert middleware[security + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"

    def test_development_uses_plain_storage(self):
        """Com DEBUG ligado não há manifesto, e exigir um quebraria o dia a dia."""
        assert settings.STORAGES["staticfiles"]["BACKEND"] == (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
        )

    def test_production_uses_the_hashed_manifest_storage(self):
        """Sem manifesto o navegador serve CSS antigo após um deploy."""
        produção = _reload_settings(DEBUG="0", SECRET_KEY="x" * 60)
        try:
            assert produção.STORAGES["staticfiles"]["BACKEND"] == (
                "whitenoise.storage.CompressedManifestStaticFilesStorage"
            )
        finally:
            _reload_settings(DEBUG="1")

    def test_collectstatic_finds_the_self_hosted_assets(self):
        """O htmx e as fontes locais precisam ser realmente coletados."""
        call_command("collectstatic", "--noinput", "--dry-run", verbosity=0)

        for caminho in [
            "static/js/htmx.min.js",
            "static/fonts/dm-sans-var.woff2",
            "static/fonts/dm-sans-italic-var.woff2",
            "static/fonts/barlow-condensed-600.woff2",
            "static/fonts/barlow-condensed-700.woff2",
            "static/css/tailwind.css",
        ]:
            assert (Path(settings.BASE_DIR) / caminho).exists(), f"{caminho} não existe"


class TestProductionHardening:
    """The security settings only take effect with DEBUG off, so test that path."""

    def test_insecure_secret_key_is_refused_in_production(self):
        """Subir em produção com a chave de desenvolvimento precisa falhar alto."""
        with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
            _reload_settings(DEBUG="0", SECRET_KEY="django-insecure-exemplo")
        _reload_settings(DEBUG="1")

    def test_cookies_are_secure_and_hsts_is_on_in_production(self):
        """Cookie de sessão em texto claro é o erro clássico de deploy."""
        produção = _reload_settings(DEBUG="0", SECRET_KEY="x" * 60)
        try:
            assert produção.SESSION_COOKIE_SECURE is True
            assert produção.CSRF_COOKIE_SECURE is True
            assert produção.SESSION_COOKIE_HTTPONLY is True
            assert produção.SECURE_CONTENT_TYPE_NOSNIFF is True
            assert produção.SECURE_HSTS_SECONDS > 0
            assert produção.X_FRAME_OPTIONS == "DENY"
            # Sem este cabeçalho o Django não reconhece o HTTPS terminado no proxy
            # e o redirect entra em loop.
            assert produção.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        finally:
            _reload_settings(DEBUG="1")

    def test_ssl_redirect_can_be_disabled_for_proxies_without_the_header(self):
        """Nem toda infraestrutura encaminha X-Forwarded-Proto; precisa haver saída."""
        produção = _reload_settings(DEBUG="0", SECRET_KEY="x" * 60, SECURE_SSL_REDIRECT="False")
        try:
            assert produção.SECURE_SSL_REDIRECT is False
        finally:
            _reload_settings(DEBUG="1")

    def test_development_stays_unhardened(self):
        """Redirect para https em desenvolvimento tornaria a aplicação inacessível."""
        assert getattr(settings, "SECURE_SSL_REDIRECT", False) is False
        assert getattr(settings, "SESSION_COOKIE_SECURE", False) is False


class TestMediaConfiguration:
    """User uploads are the only application state living outside PostgreSQL."""

    def test_media_root_and_url_are_configured(self):
        """A fase de fotos depende destes dois valores."""
        assert settings.MEDIA_URL
        assert settings.MEDIA_ROOT

    def test_media_root_is_not_inside_the_static_sources(self):
        """Mídia dentro de static/ acabaria versionada e servida como estático."""
        media_root = Path(settings.MEDIA_ROOT).resolve()
        for source in settings.STATICFILES_DIRS:
            assert Path(source).resolve() not in media_root.parents

    def test_media_is_not_wrapped_in_development(self, settings):
        """Com DEBUG ligado quem serve /media/ é o urls.py, não o WhiteNoise."""
        from config.wsgi import _servir_midia

        settings.DEBUG = True
        sentinela = object()
        assert _servir_midia(sentinela) is sentinela

    def test_media_is_served_by_whitenoise_in_production(self, settings, tmp_path):
        """Sem isso, /media/ devolve 404 em produção e as fotos somem.

        ``autorefresh`` é obrigatório: as fotos aparecem depois que o processo
        subiu, quando um administrador faz o upload.
        """
        from whitenoise import WhiteNoise

        from config.wsgi import _servir_midia

        settings.DEBUG = False
        settings.MEDIA_ROOT = tmp_path
        envolvido = _servir_midia(lambda environ, start_response: None)
        assert isinstance(envolvido, WhiteNoise)
        assert envolvido.autorefresh is True
