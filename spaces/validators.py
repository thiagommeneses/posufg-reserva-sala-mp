"""Validation rules for space cover images.

A validação acontece antes de qualquer processamento e é deliberadamente
desconfiada: a extensão do arquivo e o content-type enviado pelo navegador são
informados pelo cliente e não provam nada. Quem decide se é imagem — e qual — é
o Pillow, abrindo o conteúdo.
"""

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

#: Acima disso o upload é recusado. Uma foto de sala tratada fica em dezenas de KB;
#: 5 MB já é folga generosa para foto de celular sem tratamento.
TAMANHO_MAXIMO_BYTES = 5 * 1024 * 1024

#: Formatos aceitos, pelo que o Pillow identifica no conteúdo — não pela extensão.
#: SVG fica de fora de propósito: é XML executável, não bitmap.
FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}

#: Abaixo disto a foto fica borrada no card, que é exibido em 16:9.
LARGURA_MINIMA = 800
ALTURA_MINIMA = 450

MENSAGEM_TAMANHO = "A imagem deve ter no máximo 5 MB."
MENSAGEM_FORMATO = "Envie uma imagem em JPG, PNG ou WebP."
MENSAGEM_DIMENSAO = f"A imagem deve ter no mínimo {LARGURA_MINIMA}x{ALTURA_MINIMA} pixels."

CODIGO_TAMANHO = "imagem_muito_grande"
CODIGO_FORMATO = "formato_nao_suportado"
CODIGO_DIMENSAO = "imagem_muito_pequena"


def validar_imagem_de_capa(arquivo):
    """Validate an uploaded cover image.

    Args:
        arquivo: O arquivo enviado (``UploadedFile`` ou qualquer objeto de arquivo).

    Raises:
        ValidationError: Se exceder o tamanho, não for um formato aceito ou for
            menor que as dimensões mínimas.
    """
    tamanho = getattr(arquivo, "size", None)
    if tamanho is not None and tamanho > TAMANHO_MAXIMO_BYTES:
        raise ValidationError(MENSAGEM_TAMANHO, code=CODIGO_TAMANHO)

    arquivo.seek(0)
    try:
        with Image.open(arquivo) as imagem:
            formato = imagem.format
            largura, altura = imagem.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError(MENSAGEM_FORMATO, code=CODIGO_FORMATO) from exc
    finally:
        arquivo.seek(0)

    if formato not in FORMATOS_ACEITOS:
        raise ValidationError(MENSAGEM_FORMATO, code=CODIGO_FORMATO)

    if largura < LARGURA_MINIMA or altura < ALTURA_MINIMA:
        raise ValidationError(MENSAGEM_DIMENSAO, code=CODIGO_DIMENSAO)


#: Nomes de ícone aceitos em ``SpaceType.icon_name``.
#:
#: A lista é derivada do catálogo real em ``templates/partials/_icon.html``: um
#: nome fora dela renderizaria nada, e o administrador só descobriria olhando a
#: tela. Ao acrescentar um ícone ao partial, acrescente aqui também — há teste
#: que compara os dois.
ICONES_DISPONIVEIS = frozenset(
    {
        "arrow-left",
        "arrow-right",
        "board",
        "book",
        "briefcase",
        "calendar",
        "camera",
        "chart",
        "check",
        "chevron-down",
        "clear",
        "clock",
        "eye",
        "filter",
        "grid",
        "help",
        "home",
        "layers",
        "login",
        "logout",
        "pencil",
        "plus",
        "presentation",
        "projector",
        "refresh",
        "save",
        "sliders",
        "snowflake",
        "sparkles",
        "trash",
        "tv",
        "user-plus",
        "users",
        "video",
        "wifi",
        "wrench",
        "x",
    }
)

MENSAGEM_ICONE = "Ícone desconhecido. Use um dos nomes do catálogo da aplicação."
CODIGO_ICONE = "icone_desconhecido"


def validar_nome_de_icone(valor):
    """Validate that an icon name exists in the application catalog.

    Args:
        valor: O nome informado.

    Raises:
        ValidationError: Se o nome não estiver no catálogo.
    """
    if valor and valor not in ICONES_DISPONIVEIS:
        raise ValidationError(MENSAGEM_ICONE, code=CODIGO_ICONE)
