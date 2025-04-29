import os
from django.apps import AppConfig
from django.conf import settings

class AudioProcessingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audio_processing'

    def ready(self):
        # Ensure uploads directory exists
        uploads_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
