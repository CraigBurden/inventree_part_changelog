"""Part & Category Change Logger plugin for InvenTree."""

from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, EventMixin, SettingsMixin, UrlsMixin

from . import PLUGIN_VERSION


class PartChangeLogPlugin(AppMixin, EventMixin, SettingsMixin, UrlsMixin, InvenTreePlugin):
    """Logs creation, modification, and deletion events for parts, categories, and parameters."""

    NAME = "PartChangeLog"
    SLUG = "partchangelog"
    TITLE = "Part & Category Change Logger"
    DESCRIPTION = "Logs events for parts, categories, and parameters."
    VERSION = PLUGIN_VERSION
    AUTHOR = "Craig Burden"
    WEBSITE = "https://github.com/CraigBurden/inventree_part_changelog"
    LICENSE = "MIT"

    SETTINGS = {
        'RETENTION_DAYS': {
            'name': 'Log Retention (Days)',
            'description': 'Number of days to keep logs. Set to 0 to store logs forever.',
            'default': 0,
            'validator': int,
        },
        'TRACK_PARTS': {
            'name': 'Track Parts',
            'description': 'Log events when parts are created, modified, or deleted.',
            'default': True,
            'validator': bool,
        },
        'TRACK_CATEGORIES': {
            'name': 'Track Categories',
            'description': 'Log events when part categories are created, modified, or deleted.',
            'default': True,
            'validator': bool,
        },
        'TRACK_PARAMETERS': {
            'name': 'Track Parameters',
            'description': 'Log events when part parameters are created, modified, or deleted.',
            'default': True,
            'validator': bool,
        },
    }

    def process_event(self, event, *args, **kwargs):
        """Handle InvenTree change events for parts, categories, and parameters."""
        valid_events = (
            'part_part.',
            'part_partcategory.',
            'part_partparameter.',
            'part_parameter.',
        )

        if not event.startswith(valid_events):
            return

        event_base, action = event.split('.')
        _, item_type = event_base.split('_', 1)

        if item_type == 'part' and not self.get_setting('TRACK_PARTS'):
            return
        if item_type == 'partcategory' and not self.get_setting('TRACK_CATEGORIES'):
            return
        if item_type in ['parameter', 'partparameter'] and not self.get_setting('TRACK_PARAMETERS'):
            return

        item_id = kwargs.get('id')
        if item_id is None:
            return

        from .models import PartChangeLogEntry

        try:
            retention_days = int(self.get_setting('RETENTION_DAYS'))
        except (ValueError, TypeError):
            retention_days = 0

        if retention_days > 0:
            cutoff_date = timezone.now() - timedelta(days=retention_days)
            PartChangeLogEntry.objects.filter(timestamp__lt=cutoff_date).delete()

        related_part_id = None
        related_category_id = None

        if 'part_id' in kwargs:
            related_part_id = kwargs.get('part_id')
        elif 'part' in kwargs:
            related_part_id = kwargs.get('part')

        if action != 'deleted':
            try:
                instance = None
                for model in apps.get_models():
                    model_name = model.__name__.lower()
                    if model_name == item_type or (item_type in ['parameter', 'partparameter'] and model_name in ['parameter', 'partparameter']):
                        instance = model.objects.filter(id=item_id).first()
                        if instance:
                            break

                if instance:
                    if hasattr(instance, 'part_id') and getattr(instance, 'part_id') is not None:
                        related_part_id = getattr(instance, 'part_id')
                    elif hasattr(instance, 'part') and getattr(getattr(instance, 'part', None), 'pk', None):
                        related_part_id = getattr(instance, 'part').pk
                    elif hasattr(instance, 'content_type') and hasattr(instance, 'object_id'):
                        ct = getattr(instance, 'content_type', None)
                        if ct and getattr(ct, 'model', '') == 'part':
                            related_part_id = getattr(instance, 'object_id')

                    if hasattr(instance, 'category_id') and getattr(instance, 'category_id') is not None:
                        related_category_id = getattr(instance, 'category_id')
                    elif hasattr(instance, 'category') and getattr(getattr(instance, 'category', None), 'pk', None):
                        related_category_id = getattr(instance, 'category').pk

                    if not related_part_id and not related_category_id:
                        for field in instance._meta.get_fields():
                            if field.is_relation and field.many_to_one:
                                rel_model = field.related_model
                                if rel_model:
                                    rel_name = rel_model.__name__.lower()
                                    if rel_name == 'part' and not related_part_id:
                                        related_part_id = getattr(instance, field.attname)
                                    elif rel_name == 'partcategory' and not related_category_id:
                                        related_category_id = getattr(instance, field.attname)
            except Exception:
                pass

        PartChangeLogEntry.objects.create(
            item_type=item_type,
            item_id=item_id,
            action=action,
            related_part_id=related_part_id,
            related_category_id=related_category_id,
        )

    def setup_urls(self):
        """Register the change log API endpoint."""
        from django.urls import path
        from .views import PartChangeLogAPIView

        return [
            path('logs/', PartChangeLogAPIView.as_view(), name='partchangelog-api'),
        ]
