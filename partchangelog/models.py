"""Database models for the PartChangeLog plugin."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PartChangeLogEntry(models.Model):
    """Records a single change event for a part, category, or parameter."""

    class Meta:
        app_label = 'partchangelog'
        ordering = ['-timestamp']
        verbose_name = _('Part Change Log Entry')
        verbose_name_plural = _('Part Change Log Entries')

    item_type = models.CharField(max_length=50)
    item_id = models.IntegerField()
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now)
    related_part_id = models.IntegerField(null=True, blank=True)
    related_category_id = models.IntegerField(null=True, blank=True)
