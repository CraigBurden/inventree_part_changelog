"""Part & Category Change Logger plugin for InvenTree."""

from datetime import timedelta

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

    # Maps the item_type derived from an event name to the setting that gates it.
    TRACK_SETTINGS = {
        'part': 'TRACK_PARTS',
        'partcategory': 'TRACK_CATEGORIES',
        'parameter': 'TRACK_PARAMETERS',
        'partparameter': 'TRACK_PARAMETERS',
    }

    def process_event(self, event, *args, **kwargs):
        """Handle InvenTree change events for parts, categories, and parameters.

        Events fire as ``<db_table>.<action>``; the generalised parameter model
        keeps its historical table name and arrives as ``part_partparameter.*``.
        """
        valid_events = (
            'part_part.',
            'part_partcategory.',
            'part_partparameter.',
            'part_parameter.',
        )

        if not event.startswith(valid_events):
            return

        event_base, action = event.split('.', 1)
        _, item_type = event_base.split('_', 1)

        track_setting = self.TRACK_SETTINGS.get(item_type)
        if track_setting and not self.get_setting(track_setting):
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

        # Resolve the parent part/category while the row still exists. A delete
        # event carries only id + model and the row is already gone, so deleted
        # sub-entities are logged unlinked (they self-heal on the next part edit).
        if action != 'deleted':
            related_part_id, related_category_id = self._resolve_relations(item_type, item_id)

        PartChangeLogEntry.objects.create(
            item_type=item_type,
            item_id=item_id,
            action=action,
            related_part_id=related_part_id,
            related_category_id=related_category_id,
        )

    def _resolve_relations(self, item_type, item_id):
        """Return ``(related_part_id, related_category_id)`` for a non-deleted change.

        kicache keys its cache on the parent part, so a parameter change must
        resolve back to its part. Resolution is best-effort and never blocks
        logging the event.
        """
        try:
            if item_type == 'part':
                from part.models import Part
                part = Part.objects.filter(id=item_id).first()
                if part is not None:
                    return None, part.category_id
                return None, None

            if item_type == 'partcategory':
                return None, None

            if item_type in ('parameter', 'partparameter'):
                return self._resolve_parameter_part(item_id), None
        except Exception:
            pass

        return None, None

    def _resolve_parameter_part(self, item_id):
        """Resolve the parent part id for a parameter change.

        InvenTree 1.3+ generalised parameters: the model lives in ``common`` and
        links to its owner via ``model_type`` (a ContentType) + ``model_id``;
        only owners of type ``part`` are relevant. Older InvenTree exposed
        ``part.models.PartParameter`` with a direct ``part`` foreign key.
        """
        try:
            from common.models import Parameter
            param = Parameter.objects.filter(id=item_id).first()
            if param is not None:
                model_type = getattr(param, 'model_type', None)
                if model_type is not None and getattr(model_type, 'model', '') == 'part':
                    return getattr(param, 'model_id', None)
            return None
        except ImportError:
            pass

        try:
            from part.models import PartParameter
            param = PartParameter.objects.filter(id=item_id).first()
            if param is not None:
                return getattr(param, 'part_id', None)
        except ImportError:
            pass

        return None

    def setup_urls(self):
        """Register the change log API endpoint."""
        from django.urls import path
        from .views import PartChangeLogAPIView

        return [
            path('logs/', PartChangeLogAPIView.as_view(), name='partchangelog-api'),
        ]
