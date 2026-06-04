from django.urls import path
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta
from django.apps import apps

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from plugin import InvenTreePlugin
from plugin.mixins import EventMixin, UrlsMixin, AppMixin, SettingsMixin

class PartChangeLogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .models import PartChangeLogEntry

        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        item_types_str = request.query_params.get('item_types')
        actions_str = request.query_params.get('actions')
        concise_str = request.query_params.get('concise', 'false').lower()
        is_concise = concise_str == 'true'

        logs = PartChangeLogEntry.objects.all()

        if start_str:
            start_date = parse_datetime(start_str)
            if start_date:
                logs = logs.filter(timestamp__gte=start_date)
            else:
                return Response({'error': 'Invalid start format.'}, status=400)

        if end_str:
            end_date = parse_datetime(end_str)
            if end_date:
                logs = logs.filter(timestamp__lte=end_date)
            else:
                return Response({'error': 'Invalid end format.'}, status=400)

        if item_types_str:
            item_types = [x.strip().lower() for x in item_types_str.split(',')]
            logs = logs.filter(item_type__in=item_types)

        if actions_str:
            actions = [x.strip().lower() for x in actions_str.split(',')]
            logs = logs.filter(action__in=actions)

        if is_concise:
            # Group strictly by 'updated' (created/saved) and 'deleted'
            summary = {
                'updated': {'parts': set(), 'categories': set(), 'parameters': set()},
                'deleted': {'parts': set(), 'categories': set(), 'parameters': set()}
            }

            for log in logs:
                action = log.action
                i_type = log.item_type

                if i_type == 'partcategory':
                    type_key = 'categories'
                elif i_type in ['parameter', 'partparameter']:
                    type_key = 'parameters'
                else:
                    type_key = 'parts'

                # Bucket the action
                group = 'deleted' if action == 'deleted' else 'updated'

                # Add the primary item to its group
                summary[group][type_key].add(log.item_id)

                # --- PARENT BUBBLE-UP LOGIC (Only for Updates) ---
                if group == 'updated':
                    # Any creation/update to a parameter means its Part was updated
                    if type_key == 'parameters' and log.related_part_id:
                        summary['updated']['parts'].add(log.related_part_id)

                    # Any creation/update to a part means its Category was updated
                    if type_key == 'parts' and log.related_category_id:
                        summary['updated']['categories'].add(log.related_category_id)

            # Convert sets back to standard lists for JSON serialization
            for group in summary:
                for t_key in summary[group]:
                    summary[group][t_key] = list(summary[group][t_key])

            return Response({'concise': True, 'summary': summary})

        data = [
            {
                'id': log.id,
                'item_type': log.item_type,
                'item_id': log.item_id,
                'action': log.action,
                'related_part_id': log.related_part_id,
                'related_category_id': log.related_category_id,
                'timestamp': log.timestamp.isoformat()
            }
            for log in logs
        ]

        return Response({'count': len(data), 'logs': data})


class PartChangeLogPlugin(EventMixin, UrlsMixin, AppMixin, SettingsMixin, InvenTreePlugin):
    NAME = "PartChangeLog"
    SLUG = "partchangelog"
    TITLE = "Part & Category Change Logger"
    DESCRIPTION = "Logs events for parts, categories, and parameters."
    VERSION = "1.0.13"
    AUTHOR = "Craig Burden"

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
        }
    }

    def process_event(self, event, *args, **kwargs):
        valid_events = (
            'part_part.',
            'part_partcategory.',
            'part_partparameter.',
            'part_parameter.'
        )

        if event.startswith(valid_events):
            event_base, action = event.split('.')
            app_label, item_type = event_base.split('_', 1)

            if item_type == 'part' and not self.get_setting('TRACK_PARTS'):
                return
            if item_type == 'partcategory' and not self.get_setting('TRACK_CATEGORIES'):
                return
            if item_type in ['parameter', 'partparameter'] and not self.get_setting('TRACK_PARAMETERS'):
                return

            item_id = kwargs.get('id')

            if item_id is not None:
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

                # Fallback check for kwargs injected by InvenTree
                if 'part_id' in kwargs:
                    related_part_id = kwargs.get('part_id')
                elif 'part' in kwargs:
                    related_part_id = kwargs.get('part')

                # Only attempt database lookup for items that still exist
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
                            # Safely attempt to pull the part_id
                            if hasattr(instance, 'part_id') and getattr(instance, 'part_id') is not None:
                                related_part_id = getattr(instance, 'part_id')
                            elif hasattr(instance, 'part') and getattr(getattr(instance, 'part', None), 'pk', None):
                                related_part_id = getattr(instance, 'part').pk
                            elif hasattr(instance, 'content_type') and hasattr(instance, 'object_id'):
                                ct = getattr(instance, 'content_type', None)
                                if ct and getattr(ct, 'model', '') == 'part':
                                    related_part_id = getattr(instance, 'object_id')

                            # Safely attempt to pull the category_id
                            if hasattr(instance, 'category_id') and getattr(instance, 'category_id') is not None:
                                related_category_id = getattr(instance, 'category_id')
                            elif hasattr(instance, 'category') and getattr(getattr(instance, 'category', None), 'pk', None):
                                related_category_id = getattr(instance, 'category').pk

                            # Meta Fallback
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
                    related_category_id=related_category_id
                )

    def setup_urls(self):
        return [
            path('logs/', PartChangeLogAPIView.as_view(), name='partchangelog-api'),
        ]
