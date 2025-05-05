from django.contrib import admin
from .models import AudioProcessingTask

@admin.register(AudioProcessingTask)
class AudioProcessingTaskAdmin(admin.ModelAdmin):
    list_display = ('file_id', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('file_id', 'created_at', 'updated_at')
    search_fields = ('file_id', 'translation')
    date_hierarchy = 'created_at'  # Adds date-based navigation
    list_per_page = 50  # Optimize number of items per page
    
    # No select_related needed as this model doesn't have foreign keys
    
    def get_queryset(self, request):
        """Use our optimized custom manager methods"""
        qs = super().get_queryset(request)
        # Using our custom manager for optimization
        return qs.order_by('-created_at')
    
    def has_delete_permission(self, request, obj=None):
        """Restrict delete permission based on status"""
        if obj and obj.status == 'completed':
            # Prevent deletion of completed tasks to keep audit trail
            return False
        return super().has_delete_permission(request, obj)
