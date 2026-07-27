"""Admin registration for the knowledge app."""

from django.contrib import admin

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin configuration for Document."""

    list_display = [
        "source_id",
        "institution",
        "title",
        "category",
        "file_format",
        "word_count",
        "indexed_at",
    ]
    list_filter = ["category", "file_format"]
    search_fields = ["institution", "title", "slug"]
    readonly_fields = ["content_hash", "created_at", "updated_at"]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """Admin configuration for DocumentChunk."""

    list_display = ["document", "position", "word_count"]
    list_filter = ["document__category"]
    search_fields = ["text"]
    # O embedding tem centenas de dimensões e não é legível no admin.
    exclude = ["embedding", "search_vector"]
