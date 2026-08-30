"""Processing of space cover images.

O que chega do usuário é uma foto de celular: grande, com metadados EXIF (que
podem incluir coordenadas de onde a foto foi tirada) e possivelmente girada. O
que é servido precisa ser leve, sem metadados e na orientação certa.

Este módulo faz essa conversão. É chamado uma única vez, no ``save()`` do
:class:`~spaces.models.Space`, para que qualquer caminho de escrita — formulário
do painel, Django Admin ou API — passe pelo mesmo tratamento.
"""

import uuid

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

#: Largura máxima da imagem servida. Acima disso não há ganho visível: o maior
#: uso é a foto do topo do detalhe do espaço, com folga para telas retina.
LARGURA_MAXIMA = 1600

#: Largura da miniatura usada nos cards da grade.
LARGURA_MINIATURA = 400

#: WebP com qualidade 82 é o ponto em que o arquivo cai bastante sem artefato
#: perceptível em fotografia.
QUALIDADE_WEBP = 82

EXTENSAO = "webp"


def processar_imagem_de_capa(arquivo, largura_maxima=LARGURA_MAXIMA):
    """Normalize an uploaded image into a web-ready WebP file.

    O que acontece, em ordem:

    1. a rotação registrada no EXIF é aplicada aos pixels;
    2. todos os metadados são descartados — inclusive geolocalização;
    3. a imagem é reduzida se for mais larga que ``largura_maxima``;
    4. transparência é achatada sobre branco, porque WebP com alfa pesa mais e
       o card tem fundo sólido;
    5. o nome vira um UUID, para que o nome escolhido pelo usuário nunca chegue
       ao sistema de arquivos.

    Args:
        arquivo: Arquivo de imagem já validado.
        largura_maxima: Largura máxima do resultado, em pixels.

    Returns:
        ContentFile: Arquivo WebP pronto para ser gravado no storage.
    """
    arquivo.seek(0)
    with Image.open(arquivo) as original:
        # exif_transpose devolve a imagem já girada e sem a tag de orientação.
        imagem = ImageOps.exif_transpose(original)

        if imagem.mode in ("RGBA", "LA", "P"):
            imagem = imagem.convert("RGBA")
            fundo = Image.new("RGB", imagem.size, (255, 255, 255))
            fundo.paste(imagem, mask=imagem.split()[-1])
            imagem = fundo
        else:
            imagem = imagem.convert("RGB")

        if imagem.width > largura_maxima:
            altura = round(imagem.height * largura_maxima / imagem.width)
            imagem = imagem.resize((largura_maxima, altura), Image.LANCZOS)

        # Uma imagem nova, sem `info`, é o que garante que nenhum metadado do
        # arquivo original sobreviva ao salvamento.
        limpa = Image.new(imagem.mode, imagem.size)
        limpa.putdata(list(imagem.getdata()))

        destino = ContentFile(b"")
        limpa.save(destino, format="WEBP", quality=QUALIDADE_WEBP, method=6)

    destino.seek(0)
    return ContentFile(destino.read(), name=f"{uuid.uuid4().hex}.{EXTENSAO}")


def caminho_da_capa(instance, filename):
    """Return the storage path for a cover image.

    Args:
        instance: A instância de ``Space``.
        filename: Nome já normalizado por :func:`processar_imagem_de_capa`.

    Returns:
        str: Caminho relativo dentro de ``MEDIA_ROOT``, particionado por
        ano/mês para que o diretório não cresça indefinidamente em um nível só.
    """
    from django.utils import timezone

    hoje = timezone.localdate()
    return f"spaces/covers/{hoje.year}/{hoje.month:02d}/{filename}"
