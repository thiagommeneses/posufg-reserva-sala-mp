"""Give the known equipment attributes an icon.

Este mapeamento não é um chute, ao contrário do que seria inferir o *tipo* de um
espaço pelo nome: "Wi-Fi" recebe o ícone de Wi-Fi porque é a mesma coisa dita
duas vezes. E, se algum dia estiver errado, o custo é um desenho trocado ao lado
de um rótulo que já está escrito por extenso — não uma tela mentindo sobre
disponibilidade.

Só toca em atributos cujo nome bate exatamente e que ainda estão sem ícone.
Qualquer outro nome fica em branco, para um administrador escolher na tela.

``is_featured`` fica de fora de propósito: quais equipamentos merecem virar
filtro de primeira linha depende de como esta casa usa as salas. Existe o
comando ``sugerir_atributos_em_destaque`` para propor isso a partir dos dados
reais, com revisão humana.
"""

from django.db import migrations

ICONES = {
    "Ar-condicionado": "snowflake",
    "Projetor": "projector",
    "Quadro branco": "board",
    "TV": "tv",
    "Videoconferência": "video",
    "Webcam": "camera",
    "Wi-Fi": "wifi",
}


def aplicar_icones(apps, schema_editor):
    """Set the icon of every recognised attribute that has none yet."""
    Attribute = apps.get_model("spaces", "Attribute")
    for nome, icone in ICONES.items():
        Attribute.objects.filter(name=nome, icon_name="").update(icon_name=icone)


def remover_icones(apps, schema_editor):
    """Clear only the icons this migration set."""
    Attribute = apps.get_model("spaces", "Attribute")
    for nome, icone in ICONES.items():
        Attribute.objects.filter(name=nome, icon_name=icone).update(icon_name="")


class Migration(migrations.Migration):
    """Decorate the known attributes."""

    dependencies = [
        ("spaces", "0006_alter_attribute_options_attribute_category_and_more"),
    ]

    operations = [
        migrations.RunPython(aplicar_icones, remover_icones),
    ]
