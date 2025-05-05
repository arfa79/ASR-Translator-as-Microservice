from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
import uuid
import logging
import hashlib

# Get logger
logger = logging.getLogger('speech_translator')


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
    
    def get_or_create_cached(self, source_text, source_lang='en', target_lang='fa'):
        """
        Get a cached translation or create a new job with caching
        
        Args:
            source_text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            tuple: (translation_job, created)
        """
        # Create a cache key based on source text and languages
        cache_key = self._get_cache_key(source_text, source_lang, target_lang)
        
        # Try to get from cache first
        cached_job_id = cache.get(cache_key)
        if cached_job_id:
            try:
                return self.get(id=cached_job_id), False
            except self.model.DoesNotExist:
                # Job was deleted but cache entry remains
                cache.delete(cache_key)
        
        # Check if we have a completed job for this text/language combo
        try:
            existing_job = self.filter(
                source_text=source_text,
                source_language=source_lang,
                target_language=target_lang,
                status='completed'
            ).order_by('-created_at').first()
            
            if existing_job:
                # Store in cache for future use (1 day TTL)
                cache.set(cache_key, str(existing_job.id), 86400)
                return existing_job, False
        except Exception as e:
            logger.warning(f"Error checking for existing translation: {str(e)}")
        
        # Create a new job
        with transaction.atomic():
            new_job = self.create(
                source_text=source_text,
                source_language=source_lang,
                target_language=target_lang,
                status='received'
            )
        
        return new_job, True
    
    def _get_cache_key(self, source_text, source_lang, target_lang):
        """
        Generate a cache key for a translation
        
        Args:
            source_text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            str: Cache key
        """
        # Use MD5 hash of text for shorter keys
        text_hash = hashlib.md5(source_text.encode('utf-8')).hexdigest()
        return f"translation:{source_lang}:{target_lang}:{text_hash}"


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
    cache_hits = models.IntegerField(
        default=0,
        verbose_name=_('Cache Hits')
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
    
    @transaction.atomic
    def update_status(self, new_status):
        """
        Update job status using atomic transaction
        
        Args:
            new_status: The new status value
        """
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        logger.info(f"Job {self.id} status changed: {old_status} → {new_status}")
        return self
    
    def cache_translation(self):
        """Store this translation in cache for future use"""
        if self.status == 'completed' and self.translated_text:
            cache_key = TranslationJob.objects._get_cache_key(
                self.source_text, 
                self.source_language, 
                self.target_language
            )
            # Cache for 30 days
            cache.set(cache_key, str(self.id), 30 * 86400)
            logger.debug(f"Cached translation {self.id} with key {cache_key}")
            
    def increment_cache_hit(self):
        """Increment the counter for cache hits"""
        self.cache_hits += 1
        self.save(update_fields=['cache_hits'])
        logger.debug(f"Translation {self.id} cache hit count: {self.cache_hits}")
        return self.cache_hits
