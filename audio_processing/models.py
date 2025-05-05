import os
from django.db import models, transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Models] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class AudioProcessingTaskQuerySet(models.QuerySet):
    """Custom QuerySet for optimized queries on AudioProcessingTask"""
    
    def pending(self):
        """Filter tasks that are not completed"""
        return self.exclude(status='completed')
    
    def recent(self):
        """Get recently created tasks with proper indexing"""
        return self.order_by('-created_at')
    
    def by_status(self, status):
        """Filter tasks by status with index usage"""
        return self.filter(status=status)
    
    def older_than(self, days):
        """Get tasks older than specified days for cleanup"""
        from django.utils import timezone
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__lt=cutoff_date)
    
    def bulk_update_status(self, status, file_ids=None):
        """
        Efficiently update status of multiple tasks in one database query
        
        Args:
            status: New status to set
            file_ids: Optional list of file IDs to filter, or all if None
        """
        qs = self
        if file_ids is not None:
            qs = qs.filter(file_id__in=file_ids)
        
        with transaction.atomic():
            updated = qs.update(status=status)
            logging.info(f"Bulk updated {updated} tasks to status '{status}'")
            return updated


class AudioProcessingTaskManager(models.Manager):
    """Custom manager for AudioProcessingTask to optimize queries"""
    
    def get_queryset(self):
        return AudioProcessingTaskQuerySet(self.model, using=self._db)
    
    def pending(self):
        return self.get_queryset().pending()
    
    def recent(self):
        return self.get_queryset().recent()
    
    def by_status(self, status):
        return self.get_queryset().by_status(status)
    
    def older_than(self, days):
        return self.get_queryset().older_than(days)
    
    def bulk_create_optimized(self, tasks_data):
        """
        Efficiently create multiple tasks in one database query
        
        Args:
            tasks_data: List of dictionaries with task data
        """
        tasks = [self.model(**data) for data in tasks_data]
        with transaction.atomic():
            created = self.bulk_create(tasks)
            logging.info(f"Bulk created {len(created)} tasks")
            return created
    
    def bulk_update_status(self, status, file_ids=None):
        """
        Efficiently update status of multiple tasks
        
        Args:
            status: New status to set
            file_ids: Optional list of file IDs to filter, or all if None
        """
        return self.get_queryset().bulk_update_status(status, file_ids)


class AudioProcessingTask(models.Model):
    STATUS_CHOICES = [
        ('uploaded', _('Uploaded')),
        ('transcribing', _('Transcribing')),
        ('translating', _('Translating')),
        ('completed', _('Completed')),
    ]

    file_id = models.CharField(max_length=36, primary_key=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='uploaded', 
        db_index=True,  # Add index for faster status-based queries
        verbose_name=_('Status')
    )
    translation = models.TextField(
        null=True, 
        blank=True,
        verbose_name=_('Translation')
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        db_index=True,  # Add index for faster timestamp-based queries
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    
    # Use custom manager for optimized queries
    objects = AudioProcessingTaskManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Audio Processing Task')
        verbose_name_plural = _('Audio Processing Tasks')
        indexes = [
            models.Index(fields=['status', 'created_at']),  # Composite index for common query pattern
        ]
    
    def __str__(self):
        return f"{self.file_id} - {self.get_status_display()}"
    
    @transaction.atomic
    def update_status(self, new_status):
        """
        Update task status using atomic transaction
        
        Args:
            new_status: The new status value
        """
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        logging.info(f"Task {self.file_id} status changed: {old_status} → {new_status}")
        return self


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
