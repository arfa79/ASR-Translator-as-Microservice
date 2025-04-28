from django.db import models


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
