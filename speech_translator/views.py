from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view
from asr_translator.responses import APIResponse
from asr_translator.statuses import ErrorCode, JobStatus, Status
from .models import TranslationJob
import logging
from django.db import transaction
from django.utils import timezone

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
        source_lang = request.data.get('source_language', 'en')
        target_lang = request.data.get('target_language', 'fa')
        
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
        
        # Create a translation job in the database with optimized query
        with transaction.atomic():
            translation_job = TranslationJob.objects.create(
                source_text=text,
                source_language=source_lang,
                target_language=target_lang,
                status=JobStatus.RECEIVED
            )
        
        # In a real app, would send to message queue for processing
        # For demo, we'll simulate immediate translation
        
        # Log the translation request
        logger.info(f"Translation job {translation_job.id} received: {len(text)} characters")
        
        # Return accepted response with job ID
        return APIResponse.accepted(
            message="Translation request accepted",
            job_id=str(translation_job.id)
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
        # Get job from database with optimized query
        # Using get_object_or_404 for cleaner code
        translation_job = get_object_or_404(TranslationJob, id=job_id)
        
        # Check if job is completed
        if translation_job.status == JobStatus.COMPLETED:
            return APIResponse.success(
                data={
                    'original_text': translation_job.source_text,
                    'translated_text': translation_job.translated_text,
                    'job_id': str(translation_job.id),
                    'status': translation_job.status,
                    'source_language': translation_job.source_language,
                    'target_language': translation_job.target_language,
                    'processing_time': translation_job.processing_time
                },
                message="Translation completed"
            )
        
        # Job is still in progress
        return APIResponse.success(
            data={
                'job_id': str(translation_job.id),
                'status': translation_job.status,
                'source_language': translation_job.source_language,
                'target_language': translation_job.target_language,
                'created_at': translation_job.created_at
            },
            message=f"Translation status: {translation_job.status}"
        )
    
    except Exception as e:
        logger.exception(f"Error in translation_status: {str(e)}")
        return APIResponse.server_error(exception=e)
