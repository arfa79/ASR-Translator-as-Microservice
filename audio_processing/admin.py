from django.contrib import admin
from .models import AudioProcessingTask

@admin.register(AudioProcessingTask)
class AudioProcessingTaskAdmin(admin.ModelAdmin):
    list_display = ('file_id', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    readonly_fields = ('file_id', 'created_at', 'updated_at')
    search_fields = ('file_id',)
