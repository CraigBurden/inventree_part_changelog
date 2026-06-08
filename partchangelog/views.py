"""API views for the PartChangeLog plugin."""

from django.utils.dateparse import parse_datetime

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class PartChangeLogAPIView(APIView):
    """Returns filtered change log entries, with an optional concise summary mode."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Return change log entries, optionally filtered and summarised."""
        from .models import PartChangeLogEntry
        from .serializers import PartChangeLogEntrySerializer

        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        item_types_str = request.query_params.get('item_types')
        actions_str = request.query_params.get('actions')
        is_concise = request.query_params.get('concise', 'false').lower() == 'true'

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
            summary = {
                'updated': {'parts': set(), 'categories': set(), 'parameters': set()},
                'deleted': {'parts': set(), 'categories': set(), 'parameters': set()}
            }

            for log in logs:
                if log.item_type == 'partcategory':
                    type_key = 'categories'
                elif log.item_type in ['parameter', 'partparameter']:
                    type_key = 'parameters'
                else:
                    type_key = 'parts'

                group = 'deleted' if log.action == 'deleted' else 'updated'
                summary[group][type_key].add(log.item_id)

                if group == 'updated':
                    if type_key == 'parameters' and log.related_part_id:
                        summary['updated']['parts'].add(log.related_part_id)
                    if type_key == 'parts' and log.related_category_id:
                        summary['updated']['categories'].add(log.related_category_id)

            for group in summary:
                for t_key in summary[group]:
                    summary[group][t_key] = list(summary[group][t_key])

            return Response({'concise': True, 'summary': summary})

        data = PartChangeLogEntrySerializer(logs, many=True).data
        return Response({'count': len(data), 'logs': data})
