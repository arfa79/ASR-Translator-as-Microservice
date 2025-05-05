from django.shortcuts import render
from rest_framework.decorators import api_view
from asr_translator.responses import APIResponse
from asr_translator.statuses import ErrorCode, JobStatus, Status
import logging
import uuid
import json
from django.core.cache import cache

# Get logger
logger = logging.getLogger('speech_translator')

@api_view(['POST'])
def translate_text(request):
    """
    Endpoint to translate text from English to Persian
    
    Args:
        request: The HTTP request with text to translate
        
    Returns:
        Response: Translation response or error
    """
    try:
        # Extract text from request data
        text = request.data.get('text')
        
        if not text:
            return APIResponse.validation_error({
                'text': 'Text is required'
            })
        
        # Check if text is too long
        if len(text) > 10000:  # Arbitrary limit for example
            return APIResponse.error(
                message="Text is too long for translation",
                errors={"text": "Maximum length is 10000 characters"},
                code=ErrorCode.VALIDATION_ERROR
            )
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Store job in cache with initial status
        job_data = {
            'status': JobStatus.RECEIVED,
            'text': text,
            'result': None,
            'timestamp': None  # Will be set by worker
        }
        
        # Set cache with job data and TTL of 24 hours (in seconds)
        cache.set(f'translation_job_{job_id}', json.dumps(job_data), 86400)
        
        # In a real app, would send to message queue for processing
        # For demo, we'll simulate immediate translation
        
        # Log the translation request
        logger.info(f"Translation job {job_id} received: {len(text)} characters")
        
        # Return accepted response with job ID
        return APIResponse.accepted(
            message="Translation request accepted",
            job_id=job_id
        )
    
    except Exception as e:
        logger.exception(f"Error in translate_text: {str(e)}")
        return APIResponse.server_error(exception=e)


@api_view(['GET'])
def translation_status(request, job_id):
    """
    Check the status of a translation job
    
    Args:
        request: The HTTP request
        job_id: The ID of the translation job
        
    Returns:
        Response: Job status or error
    """
    try:
        # Get job data from cache
        job_data_str = cache.get(f'translation_job_{job_id}')
        
        if not job_data_str:
            return APIResponse.not_found(
                message=f"Translation job {job_id} not found",
                resource_type="Translation job"
            )
        
        job_data = json.loads(job_data_str)
        
        # Check if job is completed
        if job_data['status'] == JobStatus.COMPLETED:
            return APIResponse.success(
                data={
                    'original_text': job_data['text'],
                    'translated_text': job_data['result'],
                    'job_id': job_id,
                    'status': job_data['status']
                },
                message="Translation completed"
            )
        
        # Job is still in progress
        return APIResponse.success(
            data={
                'job_id': job_id,
                'status': job_data['status']
            },
            message=f"Translation status: {job_data['status']}"
        )
    
    except Exception as e:
        logger.exception(f"Error in translation_status: {str(e)}")
        return APIResponse.server_error(exception=e)
