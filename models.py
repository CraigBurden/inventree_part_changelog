from django.db import models
from django.utils import timezone

class PartChangeLogEntry(models.Model):
    item_type = models.CharField(max_length=50)
    item_id = models.IntegerField()
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now)
    related_part_id = models.IntegerField(null=True, blank=True)
    related_category_id = models.IntegerField(null=True, blank=True)

    class Meta:
        app_label = 'inventree_part_changelog'
        ordering = ['-timestamp']
