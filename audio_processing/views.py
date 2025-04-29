import uuid
import os
import json
import pika
import time
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.core.exceptions import ValidationError
from .models import AudioProcessingTask

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # 1 minute

def validate_audio_file(file):
    """Validate audio file size and format"""
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File size must not exceed {MAX_FILE_SIZE/1024/1024}MB")
    
    if not file.name.endswith('.wav'):
        raise ValidationError("Only .wav files are supported")

def check_rate_limit(request):
    """Check if request is within rate limits"""
    client_ip = request.META.get('REMOTE_ADDR')
    cache_key = f'upload_rate_{client_ip}'
    
    # Get current request count
    requests = cache.get(cache_key, 0)
    
    if requests >= RATE_LIMIT_REQUESTS:
        return False
    
    # Increment request count
    cache.set(cache_key, requests + 1, RATE_LIMIT_WINDOW)
    return True

@csrf_exempt
def upload_audio(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    # Check rate limit
    if not check_rate_limit(request):
        return JsonResponse({
            'error': f'Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds'
        }, status=429)
    
    if 'audio' not in request.FILES:
        return JsonResponse({'error': 'No audio file provided'}, status=400)
    
    audio_file = request.FILES['audio']
    
    try:
        # Validate file
        validate_audio_file(audio_file)
        
        file_id = str(uuid.uuid4())
        file_path = os.path.join('uploads', f'{file_id}.wav')
        
        # Save the file
        file_path = default_storage.save(file_path, audio_file)
        abs_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        logging.info(f"Saved audio file: {abs_file_path}")
        
        # Create task record
        AudioProcessingTask.objects.create(file_id=file_id)
        logging.info(f"Created task record with file_id: {file_id}")
        
        # Publish event
        publish_event('AudioFileUploaded', {
            'file_id': file_id,
            'file_path': abs_file_path
        })
        logging.info(f"Published AudioFileUploaded event for file_id: {file_id}")
        
        return JsonResponse({
            'status': 'accepted',
            'file_id': file_id,
            'message': 'File uploaded successfully and processing has begun'
        }, status=202)
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        if 'abs_file_path' in locals():
            cleanup_audio_file(abs_file_path)
        return JsonResponse({'error': 'Internal server error'}, status=500)

def translation_status(request):
    try:
        latest_task = AudioProcessingTask.objects.latest('created_at')
        
        response = {
            'file_id': latest_task.file_id,
        }
        
        if latest_task.status == 'completed':
            response['translation'] = latest_task.translation
        else:
            response['status'] = latest_task.status
            
        return JsonResponse(response)
        
    except AudioProcessingTask.DoesNotExist:
        return JsonResponse({'status': 'No audio uploaded yet.'})
