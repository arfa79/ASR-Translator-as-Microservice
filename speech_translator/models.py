from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class TranslationJobQuerySet(models.QuerySet):
    """Custom QuerySet for optimized queries on TranslationJob"""
    
    def pending(self):
        """Filter jobs that are not completed"""
        return self.exclude(status='completed').exclude(status='failed')
    
    def recent(self):
        """Get recently created jobs with proper indexing"""
        return self.order_by('-created_at')
    
    def by_status(self, status):
        """Filter jobs by status with index usage"""
        return self.filter(status=status)
    
    def older_than(self, days):
        """Get jobs older than specified days for cleanup"""
        from django.utils import timezone
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__lt=cutoff_date)


class TranslationJobManager(models.Manager):
    """Custom manager for TranslationJob to optimize queries"""
    
    def get_queryset(self):
        return TranslationJobQuerySet(self.model, using=self._db)
    
    def pending(self):
        return self.get_queryset().pending()
    
    def recent(self):
        return self.get_queryset().recent()
    
    def by_status(self, status):
        return self.get_queryset().by_status(status)
    
    def older_than(self, days):
        return self.get_queryset().older_than(days)


class TranslationJob(models.Model):
    """Model to store translation jobs for tracking and caching purposes"""
    
    STATUS_CHOICES = [
        ('received', _('Received')),
        ('queued', _('Queued')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('canceled', _('Canceled')),
        ('timeout', _('Timeout')),
    ]
    
    SOURCE_LANGUAGE_CHOICES = [
        ('en', _('English')),
        ('fa', _('Persian')),
        # Add more supported languages as needed
    ]
    
    TARGET_LANGUAGE_CHOICES = [
        ('en', _('English')),
        ('fa', _('Persian')),
        # Add more supported languages as needed
    ]
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name=_('Job ID')
    )
    source_text = models.TextField(
        verbose_name=_('Source Text')
    )
    translated_text = models.TextField(
        null=True, 
        blank=True,
        verbose_name=_('Translated Text')
    )
    source_language = models.CharField(
        max_length=5, 
        choices=SOURCE_LANGUAGE_CHOICES, 
        default='en',
        db_index=True,
        verbose_name=_('Source Language')
    )
    target_language = models.CharField(
        max_length=5, 
        choices=TARGET_LANGUAGE_CHOICES, 
        default='fa',
        db_index=True,
        verbose_name=_('Target Language')
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='received',
        db_index=True,
        verbose_name=_('Status')
    )
    error_message = models.TextField(
        null=True, 
        blank=True,
        verbose_name=_('Error Message')
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        db_index=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    processing_time = models.FloatField(
        null=True, 
        blank=True,
        verbose_name=_('Processing Time (seconds)')
    )
    
    # Use optimized manager
    objects = TranslationJobManager()
    
    class Meta:
        verbose_name = _('Translation Job')
        verbose_name_plural = _('Translation Jobs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source_language', 'target_language']),
        ]
    
    def __str__(self):
        return f"{self.id} - {self.get_status_display()} ({self.source_language} → {self.target_language})"
    
    def calculate_processing_time(self):
        """Calculate and store processing time if job is completed"""
        if self.status == 'completed' and not self.processing_time:
            time_diff = self.updated_at - self.created_at
            self.processing_time = time_diff.total_seconds()
            self.save(update_fields=['processing_time'])
