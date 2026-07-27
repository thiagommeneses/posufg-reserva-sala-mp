from django.db import migrations


def enable_vector(apps, schema_editor):
    """Enable the pgvector extension on PostgreSQL."""
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")


class Migration(migrations.Migration):
    """Enable the vector PostgreSQL extension."""

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(enable_vector, migrations.RunPython.noop),
    ]
