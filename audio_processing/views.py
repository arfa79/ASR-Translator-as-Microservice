import uuid
import os
import json
import pika
import time
import logging
import threading
import zlib
import base64
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.core.exceptions import ValidationError
from .models import AudioProcessingTask
from asr_translator.metrics import (
    record_audio_upload, audio_upload_duration, Timer, 
    end_to_end_duration, update_task_counts, record_error
)
from django.db.models import Count
from rest_framework.decorators import api_view
from asr_translator.responses import APIResponse
from asr_translator.statuses import ErrorCode, AudioStatus, Status
from django.core.files.base import ContentFile

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # 1 minute
STREAMING_POLL_INTERVAL = 1  # Seconds to wait between status checks for streaming responses
COMPRESSION_THRESHOLD = 1024  # Compress messages larger than 1KB
USE_MESSAGE_COMPRESSION = True  # Enable/disable message compression

# Initialize logger
logger = logging.getLogger('audio_processing')

def compress_message(message):
    """Compress a message using zlib if it's larger than threshold"""
    if not USE_MESSAGE_COMPRESSION:
        return message, False
        
    message_bytes = message.encode('utf-8')
    if len(message_bytes) < COMPRESSION_THRESHOLD:
        return message, False
        
    compressed = zlib.compress(message_bytes)
    b64_compressed = base64.b64encode(compressed).decode('ascii')
    return b64_compressed, True

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

def publish_event(event_type, payload):
    """Publish an event to RabbitMQ"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
        )
        channel = connection.channel()
        
        # Ensure exchange exists
        channel.exchange_declare(exchange=settings.RABBITMQ_EXCHANGE, exchange_type='fanout')
        
        # Add event_type to payload
        payload['event_type'] = event_type
        
        # Determine message priority based on file size if available
        priority = None
        if 'file_path' in payload and os.path.exists(payload['file_path']):
            file_size = os.path.getsize(payload['file_path'])
            # Higher priority (8-10) for smaller files (process these first)
            # Lower priority (1-3) for larger files
            if file_size < 1 * 1024 * 1024:  # Less than 1MB
                priority = 10
            elif file_size < 5 * 1024 * 1024:  # 1-5MB
                priority = 7
            elif file_size < 10 * 1024 * 1024:  # 5-10MB
                priority = 5
            else:  # Larger than 10MB
                priority = 3
            logging.info(f"Setting message priority to {priority} for file size {file_size/1024/1024:.2f}MB")
        
        # Serialize and potentially compress the message
        message_json = json.dumps(payload)
        message_data, is_compressed = compress_message(message_json)
        
        # Set message properties
        message_props = {
            'delivery_mode': 2,  # Make message persistent
        }
        
        if priority is not None:
            message_props['priority'] = priority
            
        if is_compressed:
            message_props['content_encoding'] = 'zlib+base64'
            logging.info(f"Message compressed: {len(message_json)} -> {len(message_data)} bytes")
        
        properties = pika.BasicProperties(**message_props)
        
        # Publish message with properties
        channel.basic_publish(
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key='',
            body=message_data,
            properties=properties
        )
        connection.close()
        logging.info(f"Published {event_type} event" + (" (compressed)" if is_compressed else ""))
        
    except Exception as e:
        logging.error(f"Error publishing event: {str(e)}")
        record_error('audio_processing', 'rabbitmq_publish')
        raise

def cleanup_audio_file(file_path):
    """Remove audio file from the filesystem"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logging.error(f"Error cleaning up file: {str(e)}")
        record_error('audio_processing', 'file_cleanup')

def stream_processing_status(file_id):
    """Generator function to stream processing status updates"""
    # Initial response
    yield json.dumps({
        'status': 'processing_started',
        'file_id': file_id,
        'message': 'Your audio file is now being processed'
    }) + '\n'
    
    max_attempts = 60  # Maximum 1 minute of streaming (with 1-second intervals)
    attempts = 0
    last_status = None
    
    while attempts < max_attempts:
        try:
            # Get current status
            task = AudioProcessingTask.objects.get(file_id=file_id)
            current_status = task.status
            
            # Only yield if status changed
            if current_status != last_status:
                if current_status == 'completed':
                    yield json.dumps({
                        'status': 'completed',
                        'file_id': file_id,
                        'translation': task.translation,
                        'message': 'Processing completed successfully'
                    }) + '\n'
                    break
                else:
                    yield json.dumps({
                        'status': current_status,
                        'file_id': file_id,
                        'message': f'Processing status: {current_status}'
                    }) + '\n'
                    last_status = current_status
                    
        except AudioProcessingTask.DoesNotExist:
            yield json.dumps({
                'status': 'error',
                'message': 'Task not found'
            }) + '\n'
            record_error('audio_processing', 'task_not_found')
            break
            
        # Wait before checking again
        time.sleep(STREAMING_POLL_INTERVAL)
        attempts += 1
    
    # If we reached max attempts, inform the client
    if attempts >= max_attempts:
        yield json.dumps({
            'status': 'timeout',
            'file_id': file_id,
            'message': 'Status streaming timeout reached. Check /translation/ endpoint for final result.'
        }) + '\n'

@api_view(['POST'])
def upload_audio(request):
    """
    Endpoint to upload audio files for processing
    
    Args:
        request: The HTTP request containing audio file
        
    Returns:
        Response: Upload response or error
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return APIResponse.validation_error({
                'file': 'Audio file is required'
            })
        
        audio_file = request.FILES['file']
        
        # Check file size
        if audio_file.size > settings.MAX_UPLOAD_SIZE:
            return APIResponse.error(
                message="File too large",
                errors={"file": f"Maximum file size is {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB"},
                code=ErrorCode.FILE_TOO_LARGE,
                status_code=413
            )
        
        # Check file format
        file_ext = os.path.splitext(audio_file.name)[1].lower()
        if file_ext not in settings.ALLOWED_AUDIO_FORMATS:
            return APIResponse.error(
                message="Invalid file format",
                errors={"file": f"Allowed formats: {', '.join(settings.ALLOWED_AUDIO_FORMATS)}"},
                code=ErrorCode.INVALID_FILE_FORMAT
            )
        
        # Generate unique file name
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join('uploads', unique_filename)
        
        # Save file
        saved_path = default_storage.save(file_path, ContentFile(audio_file.read()))
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Create job data
        job_data = {
            'status': AudioStatus.UPLOADED,
            'file_path': saved_path,
            'original_filename': audio_file.name,
            'file_size': audio_file.size,
            'transcription': None,
            'translation': None,
            'timestamp': None  # Will be set by worker
        }
        
        # Store job data in cache
        cache.set(f'audio_job_{job_id}', json.dumps(job_data), 86400)  # 24 hours TTL
        
        # Log the upload
        logger.info(f"Audio file uploaded: {audio_file.name}, Size: {audio_file.size}, Job ID: {job_id}")
        
        # Return success response
        return APIResponse.accepted(
            message="Audio file uploaded successfully and processing has begun",
            job_id=job_id
        )
    
    except Exception as e:
        logger.exception(f"Error processing audio upload: {str(e)}")
        return APIResponse.server_error(exception=e)

@api_view(['GET'])
def audio_job_status(request, job_id):
    """
    Check the status of an audio processing job
    
    Args:
        request: The HTTP request
        job_id: The ID of the audio processing job
        
    Returns:
        Response: Job status or error
    """
    try:
        # Get job data from cache
        job_data_str = cache.get(f'audio_job_{job_id}')
        
        if not job_data_str:
            return APIResponse.not_found(
                message=f"Audio processing job {job_id} not found",
                resource_type="Audio job"
            )
        
        job_data = json.loads(job_data_str)
        
        # Check if job is completed
        if job_data['status'] == AudioStatus.COMPLETED:
            return APIResponse.success(
                data={
                    'job_id': job_id,
                    'status': job_data['status'],
                    'filename': job_data['original_filename'],
                    'transcription': job_data['transcription'],
                    'translation': job_data['translation']
                },
                message="Audio processing completed"
            )
        
        # Check if job failed
        if job_data['status'] == AudioStatus.FAILED:
            return APIResponse.error(
                message="Audio processing failed",
                errors={"job": "Processing could not be completed"},
                code=ErrorCode.AUDIO_PROCESSING_FAILED,
                status_code=500
            )
        
        # Job is still in progress
        return APIResponse.success(
            data={
                'job_id': job_id,
                'status': job_data['status'],
                'filename': job_data['original_filename']
            },
            message=f"Audio processing status: {job_data['status']}"
        )
    
    except Exception as e:
        logger.exception(f"Error checking audio job status: {str(e)}")
        return APIResponse.server_error(exception=e)

def translation_status(request):
    try:
        # Check if client wants streaming updates
        stream_updates = request.GET.get('stream', 'false').lower() == 'true'
        
        # If streaming is requested and a file_id is provided, stream updates
        file_id = request.GET.get('file_id')
        if stream_updates and file_id:
            response = StreamingHttpResponse(
                streaming_content=stream_processing_status(file_id),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        
        # Use optimized query method to get the latest task
        latest_task = AudioProcessingTask.objects.recent().first()
        
        if not latest_task:
            return JsonResponse({'status': 'No audio uploaded yet.'})
        
        # If task is completed, record end-to-end time if timer exists
        if latest_task.status == 'completed':
            end_to_end_timer_key = f'e2e_timer_{latest_task.file_id}'
            start_time = cache.get(end_to_end_timer_key)
            if start_time:
                end_time = time.time()
                duration = end_time - start_time
                end_to_end_duration.observe(duration)
                cache.delete(end_to_end_timer_key)  # Clean up the timer
                logging.info(f"End-to-end processing took {duration:.2f} seconds for file {latest_task.file_id}")
        
        response = {
            'file_id': latest_task.file_id,
        }
        
        if latest_task.status == 'completed':
            response['translation'] = latest_task.translation
        else:
            response['status'] = latest_task.status
            
        return JsonResponse(response)
        
    except Exception as e:
        logging.error(f"Error retrieving translation status: {str(e)}")
        record_error('audio_processing', 'status_error')
        return JsonResponse({'error': 'Error retrieving translation status'}, status=500)
