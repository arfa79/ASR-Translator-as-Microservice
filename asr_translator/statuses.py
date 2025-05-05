from enum import Enum
from typing import Dict, Any, Optional, Tuple

class StatusCategory(str, Enum):
    """
    Enum of status categories to ensure consistency
    """
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class JobStatus(str, Enum):
    """
    Enum for job processing statuses
    """
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    TIMEOUT = "timeout"


class AudioStatus(str, Enum):
    """
    Enum for audio processing statuses
    """
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    CONVERTING = "converting"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ErrorCode(str, Enum):
    """
    Enum of error codes for the application
    """
    # General errors
    VALIDATION_ERROR = "validation_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"
    DATABASE_ERROR = "database_error"
    
    # Authentication errors
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    AUTHENTICATION_FAILED = "authentication_failed"
    TOKEN_EXPIRED = "token_expired"
    INVALID_TOKEN = "invalid_token"
    
    # Audio processing errors
    INVALID_FILE_FORMAT = "invalid_file_format"
    FILE_TOO_LARGE = "file_too_large"
    AUDIO_PROCESSING_FAILED = "audio_processing_failed"
    INVALID_AUDIO_CONTENT = "invalid_audio_content"
    
    # Speech recognition errors
    ASR_PROCESSING_FAILED = "asr_processing_failed"
    ASR_TIMEOUT = "asr_timeout"
    SPEECH_NOT_RECOGNIZED = "speech_not_recognized"
    
    # Translation errors
    TRANSLATION_FAILED = "translation_failed"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    TRANSLATION_TIMEOUT = "translation_timeout"
    
    # Queue and job errors
    QUEUE_FULL = "queue_full"
    JOB_NOT_FOUND = "job_not_found"
    JOB_CANCELED = "job_canceled"
    JOB_TIMEOUT = "job_timeout"
    
    # Service errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    

# Dictionary mapping error codes to HTTP status codes and default messages
ERROR_DETAILS = {
    # General errors
    ErrorCode.VALIDATION_ERROR: (400, "Validation error occurred"),
    ErrorCode.RESOURCE_NOT_FOUND: (404, "Resource not found"),
    ErrorCode.SERVER_ERROR: (500, "Internal server error"),
    ErrorCode.UNKNOWN_ERROR: (500, "An unknown error occurred"),
    ErrorCode.DATABASE_ERROR: (500, "Database error occurred"),
    
    # Authentication errors
    ErrorCode.UNAUTHORIZED: (401, "Unauthorized access"),
    ErrorCode.FORBIDDEN: (403, "Access forbidden"),
    ErrorCode.AUTHENTICATION_FAILED: (401, "Authentication failed"),
    ErrorCode.TOKEN_EXPIRED: (401, "Authentication token expired"),
    ErrorCode.INVALID_TOKEN: (401, "Invalid authentication token"),
    
    # Audio processing errors
    ErrorCode.INVALID_FILE_FORMAT: (400, "Invalid file format"),
    ErrorCode.FILE_TOO_LARGE: (413, "File too large"),
    ErrorCode.AUDIO_PROCESSING_FAILED: (500, "Audio processing failed"),
    ErrorCode.INVALID_AUDIO_CONTENT: (400, "Invalid audio content"),
    
    # Speech recognition errors
    ErrorCode.ASR_PROCESSING_FAILED: (500, "Speech recognition processing failed"),
    ErrorCode.ASR_TIMEOUT: (504, "Speech recognition timed out"),
    ErrorCode.SPEECH_NOT_RECOGNIZED: (422, "Speech could not be recognized"),
    
    # Translation errors
    ErrorCode.TRANSLATION_FAILED: (500, "Translation failed"),
    ErrorCode.UNSUPPORTED_LANGUAGE: (400, "Unsupported language"),
    ErrorCode.TRANSLATION_TIMEOUT: (504, "Translation timed out"),
    
    # Queue and job errors
    ErrorCode.QUEUE_FULL: (503, "Processing queue is full"),
    ErrorCode.JOB_NOT_FOUND: (404, "Job not found"),
    ErrorCode.JOB_CANCELED: (409, "Job was canceled"),
    ErrorCode.JOB_TIMEOUT: (504, "Job processing timed out"),
    
    # Service errors
    ErrorCode.SERVICE_UNAVAILABLE: (503, "Service unavailable"),
    ErrorCode.RATE_LIMIT_EXCEEDED: (429, "Rate limit exceeded"),
}


class Status:
    """
    Class for handling status information and error codes
    """
    
    @staticmethod
    def get_error_details(error_code: ErrorCode) -> Tuple[int, str]:
        """
        Get the HTTP status code and default message for an error code
        
        Args:
            error_code: The error code
            
        Returns:
            Tuple: (HTTP status code, default message)
        """
        return ERROR_DETAILS.get(error_code, (500, "Unknown error"))
    
    @staticmethod
    def create_error(
        error_code: ErrorCode, 
        message: Optional[str] = None, 
        details: Any = None
    ) -> Dict[str, Any]:
        """
        Create a standardized error object
        
        Args:
            error_code: The error code
            message: Custom error message (defaults to standard message)
            details: Additional error details
            
        Returns:
            Dict: Error object with code, message, and details
        """
        status_code, default_message = Status.get_error_details(error_code)
        
        error = {
            "code": error_code,
            "message": message or default_message,
            "status_code": status_code,
        }
        
        if details:
            error["details"] = details
            
        return error
    
    @staticmethod
    def get_job_status_info(
        status: JobStatus, 
        progress: Optional[float] = None, 
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a job status information object
        
        Args:
            status: The job status
            progress: Optional progress percentage (0-100)
            details: Additional status details
            
        Returns:
            Dict: Job status information object
        """
        status_info = {
            "status": status,
            "timestamp": None,  # Will be filled by the view
        }
        
        if progress is not None:
            status_info["progress"] = min(max(0, progress), 100)
            
        if details:
            status_info["details"] = details
            
        return status_info
    
    @staticmethod
    def is_final_status(status: JobStatus) -> bool:
        """
        Check if a job status is final (completed, failed, canceled)
        
        Args:
            status: The job status
            
        Returns:
            bool: True if the status is final, False otherwise
        """
        return status in (
            JobStatus.COMPLETED, 
            JobStatus.FAILED, 
            JobStatus.CANCELED,
            JobStatus.TIMEOUT
        )


# Mapping of all status codes to readable descriptions
STATUS_DESCRIPTIONS = {
    # Job statuses
    JobStatus.RECEIVED: "Job has been received by the system",
    JobStatus.QUEUED: "Job is queued for processing",
    JobStatus.PROCESSING: "Job is currently being processed",
    JobStatus.COMPLETED: "Job has been completed successfully",
    JobStatus.FAILED: "Job processing failed",
    JobStatus.CANCELED: "Job was canceled",
    JobStatus.TIMEOUT: "Job processing timed out",
    
    # Audio statuses
    AudioStatus.UPLOADED: "Audio file has been uploaded",
    AudioStatus.VALIDATING: "Audio file is being validated",
    AudioStatus.CONVERTING: "Audio file is being converted to the required format",
    AudioStatus.PROCESSING: "Audio file is being processed",
    AudioStatus.TRANSCRIBING: "Audio is being transcribed",
    AudioStatus.TRANSLATING: "Text is being translated",
    AudioStatus.COMPLETED: "Audio processing has been completed",
    AudioStatus.FAILED: "Audio processing failed",
    AudioStatus.REJECTED: "Audio file was rejected",
    
    # Error codes included for completeness
    ErrorCode.VALIDATION_ERROR: "Validation error occurred",
    ErrorCode.RESOURCE_NOT_FOUND: "Resource not found",
    ErrorCode.SERVER_ERROR: "Internal server error",
    # ... other error codes are described in ERROR_DETAILS
} 