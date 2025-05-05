from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, List, Optional, Union
from django.http import JsonResponse
import time
import logging

# Get logger
logger = logging.getLogger('django.request')

class APIResponse:
    """
    Standardized API response formatter to ensure consistent 
    response structure across all API endpoints.
    """
    
    @staticmethod
    def success(
        data: Any = None, 
        message: str = "Operation successful", 
        status_code: int = status.HTTP_200_OK,
        metadata: Dict = None
    ) -> Response:
        """
        Create a standardized success response
        
        Args:
            data: The response data
            message: Success message
            status_code: HTTP status code
            metadata: Additional metadata
            
        Returns:
            Response: Standardized DRF Response object
        """
        response_data = {
            "status": "success",
            "message": message,
            "timestamp": int(time.time()),
        }
        
        if data is not None:
            response_data["data"] = data
            
        if metadata:
            response_data["metadata"] = metadata
            
        return Response(response_data, status=status_code)
    
    @staticmethod
    def error(
        message: str = "An error occurred",
        errors: Union[List, Dict, str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = None
    ) -> Response:
        """
        Create a standardized error response
        
        Args:
            message: Error message
            errors: Detailed error information
            status_code: HTTP status code
            code: Error code for client reference
            
        Returns:
            Response: Standardized DRF Response object
        """
        # Log the error
        logger.error(f"API Error: {message} - Code: {code} - Details: {errors}")
        
        response_data = {
            "status": "error",
            "message": message,
            "timestamp": int(time.time()),
        }
        
        if errors is not None:
            response_data["errors"] = errors
            
        if code:
            response_data["code"] = code
            
        return Response(response_data, status=status_code)

    @staticmethod
    def validation_error(
        errors: Dict,
        message: str = "Validation error",
        status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> Response:
        """
        Create a response for validation errors
        
        Args:
            errors: Dictionary of field errors
            message: Error message
            status_code: HTTP status code
            
        Returns:
            Response: Standardized DRF Response object
        """
        return APIResponse.error(
            message=message,
            errors=errors,
            status_code=status_code,
            code="validation_error"
        )
    
    @staticmethod
    def not_found(
        message: str = "Resource not found",
        resource_type: str = None
    ) -> Response:
        """
        Create a not found response
        
        Args:
            message: Error message
            resource_type: Type of resource that was not found
            
        Returns:
            Response: Standardized DRF Response object
        """
        if resource_type:
            message = f"{resource_type} not found"
            
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found"
        )
    
    @staticmethod
    def server_error(
        message: str = "Internal server error",
        exception: Exception = None
    ) -> Response:
        """
        Create a server error response
        
        Args:
            message: Error message
            exception: Exception that caused the error
            
        Returns:
            Response: Standardized DRF Response object
        """
        if exception:
            logger.exception(f"Server error: {message}", exc_info=exception)
        else:
            logger.error(f"Server error: {message}")
            
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="server_error"
        )
    
    @staticmethod
    def unauthorized(
        message: str = "Unauthorized access"
    ) -> Response:
        """
        Create an unauthorized response
        
        Args:
            message: Error message
            
        Returns:
            Response: Standardized DRF Response object
        """
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized"
        )
    
    @staticmethod
    def forbidden(
        message: str = "Access forbidden"
    ) -> Response:
        """
        Create a forbidden response
        
        Args:
            message: Error message
            
        Returns:
            Response: Standardized DRF Response object
        """
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden"
        )
    
    @staticmethod
    def accepted(
        message: str = "Request accepted for processing",
        job_id: str = None
    ) -> Response:
        """
        Create a response for accepted but not yet completed requests
        
        Args:
            message: Success message
            job_id: ID of the job for tracking
            
        Returns:
            Response: Standardized DRF Response object
        """
        data = {}
        if job_id:
            data["job_id"] = job_id
            
        return APIResponse.success(
            data=data,
            message=message,
            status_code=status.HTTP_202_ACCEPTED
        )
    
    @staticmethod
    def created(
        data: Any,
        message: str = "Resource created successfully"
    ) -> Response:
        """
        Create a response for successful resource creation
        
        Args:
            data: The created resource data
            message: Success message
            
        Returns:
            Response: Standardized DRF Response object
        """
        return APIResponse.success(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED
        )
        
    @staticmethod
    def no_content() -> Response:
        """
        Create a response with no content
        
        Returns:
            Response: Standardized DRF Response object
        """
        return Response(status=status.HTTP_204_NO_CONTENT)

# For non-DRF views
def json_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
    metadata: Dict = None
) -> JsonResponse:
    """
    Create a standardized JSON response for non-DRF views
    
    Args:
        data: The response data
        message: Response message
        status_code: HTTP status code
        metadata: Additional metadata
        
    Returns:
        JsonResponse: Django JsonResponse
    """
    response_data = {
        "status": "success" if status_code < 400 else "error",
        "message": message,
        "timestamp": int(time.time()),
    }
    
    if data is not None:
        response_data["data"] = data
        
    if metadata:
        response_data["metadata"] = metadata
        
    return JsonResponse(response_data, status=status_code) 