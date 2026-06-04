"""Django app config for the PartChangeLog plugin."""

from django.apps import AppConfig


class PartChangeLogConfig(AppConfig):
    """AppConfig for the PartChangeLog plugin."""

    name = 'partchangelog'

    def ready(self):
        """Called when the app is ready."""
        ...
