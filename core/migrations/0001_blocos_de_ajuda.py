"""Cria a tabela dos blocos de ajuda institucionais.

Primeira migration do app ``core``, que até aqui não tinha modelo nenhum.

A tabela guarda só a metade da Ajuda que o código não tem como saber — uso de
auditórios, acessibilidade, orientações da casa. A metade factual (horários,
duração, check-in, no-show) não passa por aqui: é derivada da política vigente
a cada requisição, justamente para não haver uma segunda cópia das regras
envelhecendo em silêncio dentro de um campo de texto.

Nasce vazia de propósito. Um bloco com texto de exemplo seria dado falso na
tela de Ajuda — que é onde o usuário vai justamente para não ser enganado.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HelpArticle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="A pergunta ou o assunto, como o usuário procuraria.",
                        max_length=120,
                        verbose_name="Título",
                    ),
                ),
                ("slug", models.SlugField(max_length=140, unique=True)),
                (
                    "body",
                    models.TextField(
                        help_text="Escreva em parágrafos, separados por uma linha em branco. É texto puro: marcação HTML não é interpretada.",
                        verbose_name="Texto",
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Menor aparece primeiro. Empate resolve por título.",
                        verbose_name="Ordem",
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(
                        default=True,
                        help_text="Desmarque para tirar o bloco da tela de Ajuda sem apagar o texto.",
                        verbose_name="Publicado",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Bloco de ajuda",
                "verbose_name_plural": "Blocos de ajuda",
                "ordering": ("sort_order", "title"),
            },
        ),
    ]
