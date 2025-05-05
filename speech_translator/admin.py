from django.contrib import admin
from .models import TranslationJob

@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'source_language', 'target_language', 'processing_time', 'created_at')
    list_filter = ('status', 'source_language', 'target_language', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'processing_time')
    search_fields = ('id', 'source_text', 'translated_text', 'error_message')
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        (None, {
            'fields': ('id', 'status')
        }),
        ('Translation Details', {
            'fields': ('source_language', 'target_language', 'processing_time')
        }),
        ('Content', {
            'fields': ('source_text', 'translated_text'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Use our optimized custom manager methods"""
        qs = super().get_queryset(request)
        # Using our custom manager method for better performance
        return qs.order_by('-created_at')
    
    # Add action to recalculate processing time for selected jobs
    actions = ['recalculate_processing_time']
    
    def recalculate_processing_time(self, request, queryset):
        """Recalculate processing time for all selected jobs"""
        for job in queryset.filter(status='completed'):
            job.calculate_processing_time()
        self.message_user(request, f"Processing time recalculated for {queryset.filter(status='completed').count()} jobs")
    recalculate_processing_time.short_description = "Recalculate processing time"
