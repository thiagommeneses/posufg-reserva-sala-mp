"""Dias da semana em que o prédio abre.

Antes desta migration a política sabia a que horas o prédio abre, mas não em
que dias — e o sistema oferecia horário no domingo porque ninguém tinha dito
que não. O padrão aqui é de segunda a sexta.

Isto muda comportamento visível no deploy: sábado e domingo deixam de ter
horários oferecidos. A **recusa** na gravação continua atrás de
``enforce_window``, que segue desligado por padrão — nenhuma reserva existente
passa a ser rejeitada por causa desta migration. Uma instalação que de fato
abre no fim de semana marca os dias na tela de Política de reserva.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0006_bookingpolicy_no_show_threshold_minutes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_friday",
            field=models.BooleanField(default=True, verbose_name="Sexta-feira"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_monday",
            field=models.BooleanField(default=True, verbose_name="Segunda-feira"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_saturday",
            field=models.BooleanField(default=False, verbose_name="Sábado"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_sunday",
            field=models.BooleanField(default=False, verbose_name="Domingo"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_thursday",
            field=models.BooleanField(default=True, verbose_name="Quinta-feira"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_tuesday",
            field=models.BooleanField(default=True, verbose_name="Terça-feira"),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="opens_wednesday",
            field=models.BooleanField(default=True, verbose_name="Quarta-feira"),
        ),
    ]
