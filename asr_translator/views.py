from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .logging import get_prometheus_metrics
import json
import logging

# Get logger
logger = logging.getLogger('django')

@csrf_exempt
def metrics_endpoint(request):
    """
    Endpoint to expose Prometheus metrics for scraping.
    This is a simple implementation; in production, use the official
    Prometheus client library with proper formatting.
    
    Args:
        request: The HTTP request
        
    Returns:
        JsonResponse: Metrics in JSON format
    """
    if request.method != 'GET':
        return JsonResponse({
            'error': 'Method not allowed'
        }, status=405)
    
    # Check if the request has a valid token if we're not in debug mode
    if not settings.DEBUG:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
        
        if not token or token != settings.METRICS_TOKEN:
            logger.warning(f"Unauthorized metrics access attempt from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Unauthorized access'
            }, status=401)
    
    # Get current metrics
    metrics = get_prometheus_metrics()
    
    return JsonResponse(metrics)

@csrf_exempt
def health_check(request):
    """
    Simple health check endpoint to verify the service is running.
    
    Args:
        request: The HTTP request
        
    Returns:
        JsonResponse: Health status information
    """
    if request.method != 'GET':
        return JsonResponse({
            'error': 'Method not allowed'
        }, status=405)
    
    # Add basic health information
    health_status = {
        'status': 'healthy',
        'services': {
            'web': 'up',
            'database': 'up',
            'redis': 'up' if settings.REDIS_HOST != 'dummy' else 'not configured',
            'rabbitmq': 'up',  # Placeholder - actual check should be implemented
        }
    }
    
    # Check if services are actually available
    try:
        # Database check - simple query to verify connection
        from django.db import connection
        from django.db.utils import OperationalError
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except OperationalError:
            health_status['services']['database'] = 'down'
            health_status['status'] = 'degraded'
    except Exception as e:
        logger.error(f"Error checking database health: {str(e)}")
        health_status['services']['database'] = 'unknown'
        health_status['status'] = 'degraded'
    
    # Redis check if configured
    if settings.REDIS_HOST != 'dummy':
        try:
            from django_redis import get_redis_connection
            
            try:
                redis_conn = get_redis_connection("default")
                redis_conn.ping()
            except Exception:
                health_status['services']['redis'] = 'down'
                health_status['status'] = 'degraded'
        except Exception as e:
            logger.error(f"Error checking Redis health: {str(e)}")
            health_status['services']['redis'] = 'unknown'
            health_status['status'] = 'degraded'
    
    # RabbitMQ check
    try:
        import pika
        
        try:
            # Create a connection to check if RabbitMQ is available
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                connection_attempts=1,
                socket_timeout=2
            )
            connection = pika.BlockingConnection(parameters)
            connection.close()
        except Exception:
            health_status['services']['rabbitmq'] = 'down'
            health_status['status'] = 'degraded'
    except Exception as e:
        logger.error(f"Error checking RabbitMQ health: {str(e)}")
        health_status['services']['rabbitmq'] = 'unknown'
        health_status['status'] = 'degraded'
    
    # Return health status with appropriate HTTP status code
    status_code = 200 if health_status['status'] == 'healthy' else 503
    
    return JsonResponse(health_status, status=status_code) 