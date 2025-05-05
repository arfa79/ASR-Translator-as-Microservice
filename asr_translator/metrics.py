"""
Metrics collection for the ASR-Translator service.
This module initializes Prometheus metrics and provides functions to record metrics.
"""

import time
import threading
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
import pika
import psutil
import logging
import os
from django.conf import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Metrics] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Metrics configuration
METRICS_PORT = int(os.environ.get('METRICS_PORT', 8000))
COLLECTION_INTERVAL = int(os.environ.get('METRICS_COLLECTION_INTERVAL', 15))  # seconds

# Initialize metrics

# Counters
audio_uploads_total = Counter('audio_uploads_total', 'Total number of audio file uploads')
asr_requests_total = Counter('asr_requests_total', 'Total number of ASR requests')
translation_requests_total = Counter('translation_requests_total', 'Total number of translation requests')
errors_total = Counter('errors_total', 'Total number of errors', ['service', 'error_type'])

# Histograms for timing
audio_upload_duration = Histogram('audio_upload_duration_seconds', 'Time taken to upload audio files', 
                                 buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0])
asr_processing_duration = Histogram('asr_processing_duration_seconds', 'Time taken for ASR processing',
                                   buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0])
translation_duration = Histogram('translation_duration_seconds', 'Time taken for translation',
                                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0])
end_to_end_duration = Histogram('end_to_end_duration_seconds', 'Time taken for complete processing pipeline',
                               buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0])

# Gauges for current state
queue_size = Gauge('rabbitmq_queue_size', 'Number of messages in RabbitMQ queue', ['queue_name'])
memory_usage = Gauge('memory_usage_bytes', 'Memory usage in bytes', ['service'])
cpu_usage = Gauge('cpu_usage_percent', 'CPU usage percentage', ['service'])
audio_processing_tasks = Gauge('audio_processing_tasks', 'Number of audio processing tasks', ['status'])
cache_hit_ratio = Gauge('cache_hit_ratio', 'Cache hit ratio for translation cache')

# Timer context manager
class Timer:
    def __init__(self, metric):
        self.metric = metric
        
    def __enter__(self):
        self.start = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.metric.observe(time.time() - self.start)

def start_metrics_server():
    """Start the metrics HTTP server"""
    try:
        start_http_server(METRICS_PORT)
        logging.info(f"Metrics server started on port {METRICS_PORT}")
    except Exception as e:
        logging.error(f"Failed to start metrics server: {str(e)}")

def collect_queue_metrics():
    """Collect queue metrics from RabbitMQ"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                connection_attempts=1,
                socket_timeout=2
            )
        )
        channel = connection.channel()
        
        # Get queue information
        queues = ['asr_processing_queue', 'translation_queue']
        for queue_name in queues:
            try:
                queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
                queue_size.labels(queue_name=queue_name).set(queue_info.method.message_count)
            except Exception as e:
                logging.warning(f"Failed to get metrics for queue {queue_name}: {str(e)}")
                
        connection.close()
    except Exception as e:
        logging.error(f"Failed to collect RabbitMQ metrics: {str(e)}")

def collect_system_metrics():
    """Collect system metrics (CPU, memory)"""
    try:
        # Get process information for different services
        process = psutil.Process()
        
        # Record CPU and memory usage for current process
        service_name = os.environ.get('SERVICE_NAME', 'unknown')
        memory_usage.labels(service=service_name).set(process.memory_info().rss)
        cpu_usage.labels(service=service_name).set(process.cpu_percent(interval=0.1))
        
    except Exception as e:
        logging.error(f"Failed to collect system metrics: {str(e)}")

def collect_metrics_periodically():
    """Collect metrics at regular intervals"""
    while True:
        try:
            collect_queue_metrics()
            collect_system_metrics()
            
            # Sleep until next collection
            time.sleep(COLLECTION_INTERVAL)
        except Exception as e:
            logging.error(f"Error in metrics collection: {str(e)}")
            time.sleep(COLLECTION_INTERVAL)

def start_metrics_collection():
    """Start the metrics collection in a background thread"""
    # First start the HTTP server
    start_metrics_server()
    
    # Then start the collection thread
    collection_thread = threading.Thread(
        target=collect_metrics_periodically,
        daemon=True,
        name="metrics-collection"
    )
    collection_thread.start()
    logging.info("Metrics collection started")
    
    return collection_thread

# Utility functions to record metrics in other modules
def record_audio_upload(file_size):
    """Record metrics for an audio upload"""
    audio_uploads_total.inc()
    # Additional metrics like file size can be added here

def record_asr_request():
    """Record metrics for an ASR request"""
    asr_requests_total.inc()
    
def record_translation_request():
    """Record metrics for a translation request"""
    translation_requests_total.inc()
    
def record_error(service, error_type):
    """Record an error"""
    errors_total.labels(service=service, error_type=error_type).inc()

def update_cache_hit_ratio(hits, misses):
    """Update the cache hit ratio"""
    total = hits + misses
    if total > 0:
        cache_hit_ratio.set(hits / total)

def update_task_counts(status_counts):
    """Update counts of tasks by status"""
    for status, count in status_counts.items():
        audio_processing_tasks.labels(status=status).set(count) 