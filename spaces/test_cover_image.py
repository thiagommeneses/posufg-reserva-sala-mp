"""Tests for space cover images.

Upload de arquivo é uma superfície de ataque e uma fonte silenciosa de lixo em
disco. Estes testes cobrem as duas coisas além do caminho feliz: o que precisa
ser recusado, e o que precisa ser apagado.
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from spaces.images import LARGURA_MAXIMA, processar_imagem_de_capa
from spaces.models import Space
from spaces.validators import (
    CODIGO_DIMENSAO,
    CODIGO_FORMATO,
    CODIGO_TAMANHO,
    validar_imagem_de_capa,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def media_isolada(settings, tmp_path):
    """Point MEDIA_ROOT at a per-test temporary directory.

    Cada teste grava em um diretório próprio: nenhum suja o repositório e
    nenhum depende do que outro deixou para trás.

    Args:
        settings: Fixture do pytest-django que permite alterar settings.
        tmp_path: Diretório temporário exclusivo do teste.

    Returns:
        Path: O MEDIA_ROOT em uso.
    """
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def imagem_em_memoria(largura=1200, altura=800, formato="JPEG", modo="RGB", exif=None):
    """Build an in-memory image file for upload.

    Args:
        largura: Largura em pixels.
        altura: Altura em pixels.
        formato: Formato do Pillow ("JPEG", "PNG", "WEBP", "GIF"...).
        modo: Modo de cor.
        exif: Bytes EXIF opcionais a embutir.

    Returns:
        SimpleUploadedFile: Arquivo pronto para ser enviado num formulário.
    """
    imagem = Image.new(modo, (largura, altura), (200, 40, 60) if modo == "RGB" else None)
    buffer = io.BytesIO()
    parametros = {"exif": exif} if exif else {}
    imagem.save(buffer, format=formato, **parametros)
    buffer.seek(0)
    extensao = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[formato]
    tipo = f"image/{'jpeg' if formato == 'JPEG' else extensao}"
    return SimpleUploadedFile(f"foto.{extensao}", buffer.read(), content_type=tipo)


class TestValidacao:
    """What must be refused, and why."""

    def test_aceita_jpeg_png_e_webp(self):
        """Os três formatos previstos passam."""
        for formato in ["JPEG", "PNG", "WEBP"]:
            validar_imagem_de_capa(imagem_em_memoria(formato=formato))

    def test_recusa_arquivo_que_nao_e_imagem(self):
        """Um texto renomeado para .jpg precisa ser recusado pelo conteúdo."""
        falso = SimpleUploadedFile("foto.jpg", b"isto nao e uma imagem", content_type="image/jpeg")
        with pytest.raises(ValidationError) as erro:
            validar_imagem_de_capa(falso)
        assert erro.value.code == CODIGO_FORMATO

    def test_recusa_formato_fora_da_lista(self):
        """GIF é imagem de verdade, mas não está entre os formatos aceitos."""
        with pytest.raises(ValidationError) as erro:
            validar_imagem_de_capa(imagem_em_memoria(formato="GIF", modo="P"))
        assert erro.value.code == CODIGO_FORMATO

    def test_recusa_imagem_pequena_demais(self):
        """Abaixo de 800x450 a foto fica borrada no card."""
        with pytest.raises(ValidationError) as erro:
            validar_imagem_de_capa(imagem_em_memoria(largura=400, altura=300))
        assert erro.value.code == CODIGO_DIMENSAO

    def test_recusa_arquivo_acima_do_limite(self):
        """O limite de 5 MB é checado antes de abrir o arquivo."""
        grande = imagem_em_memoria()
        grande.size = 6 * 1024 * 1024
        with pytest.raises(ValidationError) as erro:
            validar_imagem_de_capa(grande)
        assert erro.value.code == CODIGO_TAMANHO

    def test_deixa_o_arquivo_rebobinado(self):
        """Depois de validar, o arquivo precisa poder ser lido de novo."""
        arquivo = imagem_em_memoria()
        validar_imagem_de_capa(arquivo)
        assert arquivo.tell() == 0


class TestProcessamento:
    """The stored file is never the file the user uploaded."""

    def test_converte_para_webp(self):
        """Toda capa é servida em WebP, independentemente do que entrou."""
        resultado = processar_imagem_de_capa(imagem_em_memoria(formato="PNG"))
        assert resultado.name.endswith(".webp")
        with Image.open(resultado) as imagem:
            assert imagem.format == "WEBP"

    def test_reduz_imagem_larga_demais(self):
        """Nada é servido acima da largura máxima."""
        resultado = processar_imagem_de_capa(imagem_em_memoria(largura=4000, altura=3000))
        with Image.open(resultado) as imagem:
            assert imagem.width == LARGURA_MAXIMA

    def test_preserva_imagem_menor_que_o_limite(self):
        """Uma imagem já pequena não é ampliada."""
        resultado = processar_imagem_de_capa(imagem_em_memoria(largura=1000, altura=600))
        with Image.open(resultado) as imagem:
            assert imagem.width == 1000

    def test_nome_do_arquivo_vira_uuid(self):
        """O nome escolhido pelo usuário nunca chega ao sistema de arquivos."""
        arquivo = imagem_em_memoria()
        arquivo.name = "../../etc/passwd.jpg"
        resultado = processar_imagem_de_capa(arquivo)
        assert "passwd" not in resultado.name
        assert "/" not in resultado.name

    def test_remove_metadados(self):
        """EXIF pode carregar geolocalização; nada disso sobrevive."""
        original = Image.new("RGB", (1200, 800))
        exif = original.getexif()
        exif[271] = "Camera de Teste"  # Make
        exif[274] = 6  # Orientation
        buffer = io.BytesIO()
        original.save(buffer, format="JPEG", exif=exif.tobytes())
        buffer.seek(0)
        entrada = SimpleUploadedFile("foto.jpg", buffer.read(), content_type="image/jpeg")

        resultado = processar_imagem_de_capa(entrada)
        with Image.open(resultado) as imagem:
            assert not imagem.getexif()

    def test_achata_transparencia_sobre_branco(self):
        """PNG com alfa vira RGB: o card tem fundo sólido e o WebP fica menor."""
        resultado = processar_imagem_de_capa(imagem_em_memoria(formato="PNG", modo="RGBA"))
        with Image.open(resultado) as imagem:
            assert imagem.mode == "RGB"


@pytest.mark.django_db
class TestArmazenamento:
    """Files must land in the right place — and leave when they should."""

    def test_salva_a_capa_processada(self):
        """O arquivo gravado é o processado, não o enviado."""
        espaco = Space.objects.create(
            name="Sala com Foto",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(formato="PNG"),
        )
        assert espaco.cover_image.name.endswith(".webp")
        assert "spaces/covers/" in espaco.cover_image.name
        assert espaco.cover_image.storage.exists(espaco.cover_image.name)

    def test_nao_reprocessa_ao_salvar_de_novo(self):
        """Recarregar e salvar não pode degradar a imagem a cada gravação."""
        espaco = Space.objects.create(
            name="Sala Estável",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(),
        )
        nome_original = espaco.cover_image.name

        recarregado = Space.objects.get(pk=espaco.pk)
        recarregado.capacity = 10
        recarregado.save()

        assert recarregado.cover_image.name == nome_original

    def test_apaga_o_arquivo_anterior_ao_trocar_a_capa(self):
        """Trocar a foto não pode deixar a antiga ocupando o volume."""
        espaco = Space.objects.create(
            name="Sala que Troca",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(),
        )
        nome_antigo = espaco.cover_image.name
        armazenamento = espaco.cover_image.storage

        espaco.cover_image = imagem_em_memoria(formato="PNG")
        espaco.save()

        assert espaco.cover_image.name != nome_antigo
        assert not armazenamento.exists(nome_antigo)
        assert armazenamento.exists(espaco.cover_image.name)

    def test_apaga_o_arquivo_ao_excluir_o_espaco(self):
        """Espaço excluído não deixa foto órfã."""
        espaco = Space.objects.create(
            name="Sala Efêmera",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(),
        )
        nome = espaco.cover_image.name
        armazenamento = espaco.cover_image.storage

        espaco.delete()

        assert not armazenamento.exists(nome)

    def test_espaco_sem_foto_continua_valido(self):
        """A foto é opcional — os espaços já cadastrados não têm nenhuma."""
        espaco = Space.objects.create(name="Sala Sem Foto", capacity=4, location="Bloco B")
        assert not espaco.cover_image


@pytest.mark.django_db
class TestUploadPeloPainel:
    """The admin screen is the real entry point for photos."""

    @pytest.fixture
    def admin(self):
        """Create a staff user."""
        return User.objects.create_user(
            username="fotoadmin", password="senha-de-teste", is_staff=True
        )

    @pytest.fixture
    def comum(self):
        """Create a non-staff user."""
        return User.objects.create_user(username="fotouser", password="senha-de-teste")

    def test_formulario_declara_multipart(self, client, admin):
        """Sem enctype multipart o navegador não envia o arquivo."""
        client.force_login(admin)
        response = client.get("/admin-dashboard/spaces/new/")
        assert response.status_code == 200
        assert 'enctype="multipart/form-data"' in response.content.decode()

    def test_admin_envia_foto_pelo_formulario(self, client, admin):
        """Caminho feliz ponta a ponta pelo painel."""
        client.force_login(admin)
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Sala Enviada",
                "description": "",
                "capacity": 10,
                "location": "Bloco C",
                "is_active": "on",
                "cover_image": imagem_em_memoria(),
            },
        )
        assert response.status_code == 302
        espaco = Space.objects.get(name="Sala Enviada")
        assert espaco.cover_image
        assert espaco.cover_image.name.endswith(".webp")

    def test_formulario_recusa_arquivo_invalido_com_mensagem(self, client, admin):
        """O erro precisa voltar no formulário, em português, sem criar o espaço."""
        client.force_login(admin)
        falso = SimpleUploadedFile("foto.jpg", b"nao sou imagem", content_type="image/jpeg")
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Sala Recusada",
                "description": "",
                "capacity": 10,
                "location": "Bloco C",
                "is_active": "on",
                "cover_image": falso,
            },
        )
        assert response.status_code == 200
        assert not Space.objects.filter(name="Sala Recusada").exists()

    def test_usuario_comum_nao_envia_foto(self, client, comum):
        """Upload é operação de administrador."""
        client.force_login(comum)
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {"name": "Sala Proibida", "capacity": 4, "location": "X"},
        )
        assert response.status_code == 403
        assert not Space.objects.filter(name="Sala Proibida").exists()


@pytest.mark.django_db
class TestApiEInterface:
    """The photo has to reach both the API and the screens."""

    def test_serializer_devolve_url_absoluta(self):
        """Um cliente fora do host precisa de URL completa."""
        usuario = User.objects.create_user(username="apifoto", password="senha-de-teste")
        Space.objects.create(
            name="Sala API",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(),
        )
        api = APIClient()
        api.force_authenticate(user=usuario)
        response = api.get("/api/v1/spaces/")
        assert response.status_code == 200
        dados = next(s for s in response.data if s["name"] == "Sala API")
        assert dados["cover_image_url"].startswith("http")
        assert ".webp" in dados["cover_image_url"]

    def test_serializer_devolve_none_sem_foto(self):
        """Sem foto o campo é null — quem consome decide o fallback."""
        usuario = User.objects.create_user(username="apisemfoto", password="senha-de-teste")
        Space.objects.create(name="Sala Sem Foto API", capacity=8, location="Bloco A")
        api = APIClient()
        api.force_authenticate(user=usuario)
        response = api.get("/api/v1/spaces/")
        dados = next(s for s in response.data if s["name"] == "Sala Sem Foto API")
        assert dados["cover_image_url"] is None

    def test_card_mostra_a_foto_quando_existe(self, client):
        """A grade exibe a imagem com alt descritivo."""
        usuario = User.objects.create_user(username="gradefoto", password="senha-de-teste")
        Space.objects.create(
            name="Sala Visível",
            capacity=8,
            location="Bloco A",
            cover_image=imagem_em_memoria(),
        )
        client.force_login(usuario)
        html = client.get("/spaces/").content.decode()
        assert "Foto do espaço Sala Visível" in html
        assert 'class="absolute inset-0 h-full w-full object-cover' in html

    def test_card_sem_foto_usa_marcador_e_nao_quebra(self, client):
        """Espaço sem foto não pode render um <img> apontando para lugar nenhum."""
        usuario = User.objects.create_user(username="gradesemfoto", password="senha-de-teste")
        Space.objects.create(name="Sala Sem Imagem", capacity=8, location="Bloco A")
        client.force_login(usuario)
        html = client.get("/spaces/").content.decode()
        assert "Espaço sem foto cadastrada" in html
        assert "Foto do espaço Sala Sem Imagem" not in html

    def test_area_da_imagem_reserva_espaco_antes_de_carregar(self, client):
        """A proporção fixa é o que impede o card de pular quando a foto chega."""
        usuario = User.objects.create_user(username="semlayoutshift", password="senha-de-teste")
        Space.objects.create(name="Sala Estável", capacity=8, location="Bloco A")
        client.force_login(usuario)
        html = client.get("/spaces/").content.decode()
        assert "aspect-[16/9]" in html
