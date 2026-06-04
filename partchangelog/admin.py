"""Admin site configuration for the PartChangeLog plugin."""

from django.contrib import admin

from .models import PartChangeLogEntry


@admin.register(PartChangeLogEntry)
class PartChangeLogEntryAdmin(admin.ModelAdmin):
    """Admin interface for PartChangeLogEntry."""

    list_display = ('item_type', 'item_id', 'action', 'timestamp', 'related_part_id', 'related_category_id')
    list_filter = ('item_type', 'action')
    ordering = ('-timestamp',)
