"""API serializers for the PartChangeLog plugin."""

from rest_framework import serializers

from .models import PartChangeLogEntry


class PartChangeLogEntrySerializer(serializers.ModelSerializer):
    """Serializer for PartChangeLogEntry model instances."""

    class Meta:
        model = PartChangeLogEntry
        fields = ['id', 'item_type', 'item_id', 'action', 'related_part_id', 'related_category_id', 'timestamp']
