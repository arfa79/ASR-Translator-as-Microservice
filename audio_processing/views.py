import uuid
import os
import json
import pika
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from .models import AudioProcessingTask

def publish_event(event_type, payload):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    )
    channel = connection.channel()
    channel.exchange_declare(exchange=settings.RABBITMQ_EXCHANGE, exchange_type='fanout')
    
    message = {
        'event_type': event_type,
        **payload
    }
    channel.basic_publish(
        exchange=settings.RABBITMQ_EXCHANGE,
        routing_key='',
        body=json.dumps(message)
    )
    connection.close()

@csrf_exempt
def upload_audio(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    if 'audio' not in request.FILES:
        return JsonResponse({'error': 'No audio file provided'}, status=400)
    
    audio_file = request.FILES['audio']
    if not audio_file.name.endswith('.wav'):
        return JsonResponse({'error': 'Only .wav files are supported'}, status=400)
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join('uploads', f'{file_id}.wav')
    
    # Save the file
    file_path = default_storage.save(file_path, audio_file)
    abs_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    # Create task record
    AudioProcessingTask.objects.create(file_id=file_id)
    
    # Publish event
    publish_event('AudioFileUploaded', {
        'file_id': file_id,
        'file_path': abs_file_path
    })
    
    return JsonResponse({
        'status': 'accepted',
        'file_id': file_id
    }, status=202)

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
