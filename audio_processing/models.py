import os
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.conf import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Models] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class AudioProcessingTask(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('transcribing', 'Transcribing'),
        ('translating', 'Translating'),
        ('completed', 'Completed'),
    ]

    file_id = models.CharField(max_length=36, primary_key=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    translation = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


@receiver(pre_delete, sender=AudioProcessingTask)
def cleanup_task_files(sender, instance, **kwargs):
    """Clean up associated audio files when a task is deleted"""
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', f'{instance.file_id}.wav')
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Cleaned up audio file for task {instance.file_id}")
    except Exception as e:
        logging.error(f"Error cleaning up file for task {instance.file_id}: {str(e)}")
