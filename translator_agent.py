import os
import json
import pika
import django
import time
import logging
import threading
import hashlib
import zlib
import base64
from argostranslate import package, translate
import redis

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, CPU affinity settings will be disabled")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Translation Service] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asr_translator.settings')
django.setup()

from django.conf import settings
from audio_processing.models import AudioProcessingTask
from asr_translator.metrics import (
    record_translation_request, translation_duration, Timer,
    record_error, memory_usage, cpu_usage, update_cache_hit_ratio
)

# Redis configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_ENABLED = os.environ.get('REDIS_ENABLED', 'True').lower() in ('true', '1', 't')
CACHE_EXPIRY = 3600 * 24 * 1  # Cache for 1 day by default
CPU_AFFINITY_ENABLED = os.environ.get('CPU_AFFINITY_ENABLED', 'True').lower() in ('true', '1', 't')
USE_MESSAGE_COMPRESSION = True  # Enable/disable message compression
COMPRESSION_THRESHOLD = 1024  # Compress messages larger than 1KB

# Initialize Redis client if enabled
redis_client = None
if REDIS_ENABLED:
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        redis_client.ping()  # Test connection
        logging.info(f"Redis cache connected successfully: {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logging.warning(f"Redis cache connection failed: {str(e)}")
        logging.warning("Translation caching will be disabled")
        redis_client = None

# Metrics for cache
cache_hits = 0
cache_misses = 0

def decompress_message(message, content_encoding=None):
    """Decompress a message if it's compressed"""
    if not content_encoding or 'zlib+base64' not in content_encoding:
        return message
        
    try:
        # Decode base64, then decompress
        decoded = base64.b64decode(message)
        decompressed = zlib.decompress(decoded)
        return decompressed.decode('utf-8')
    except Exception as e:
        logging.error(f"Error decompressing message: {str(e)}")
        record_error('translator', 'decompression_error')
        return message

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

def set_cpu_affinity():
    """Set CPU affinity for the Translation service if psutil is available"""
    if not PSUTIL_AVAILABLE or not CPU_AFFINITY_ENABLED:
        return
    
    try:
        # Get the current process
        process = psutil.Process()
        
        # Get the number of CPU cores
        cpu_count = psutil.cpu_count(logical=False)  # Physical cores only
        if cpu_count is None:
            cpu_count = psutil.cpu_count(logical=True)  # Logical cores as fallback
        
        if cpu_count is None or cpu_count < 2:
            logging.warning("Not enough CPU cores for affinity settings")
            return
        
        # For Translation service, use the second half of available cores
        # This complements the ASR service which uses the first half
        cores_to_use = list(range((cpu_count + 1) // 2, cpu_count))
        
        # Set affinity
        process.cpu_affinity(cores_to_use)
        logging.info(f"Set CPU affinity to cores: {cores_to_use}")
    except Exception as e:
        logging.error(f"Error setting CPU affinity: {str(e)}")
        record_error('translator', 'cpu_affinity_error')

def setup_translation():
    """Setup Argostranslate with English to Persian translation"""
    try:
        logging.info("Starting translation setup...")
        package.update_package_index()
        available_packages = package.get_available_packages()
        package_to_install = next(
            (pkg for pkg in available_packages if pkg.from_code == "en" and pkg.to_code == "fa"),
            None
        )
        
        if not package_to_install:
            logging.error("English to Persian translation package not found")
            record_error('translator', 'translation_package_not_found')
            raise RuntimeError(
                "English to Persian translation package not found. "
                "Please check your internet connection and try again."
            )
        
        logging.info("Installing English to Persian translation package...")
        package.install_from_path(package_to_install.download())
        logging.info("Translation setup completed successfully")
        
    except Exception as e:
        logging.error(f"Error setting up translation: {str(e)}")
        record_error('translator', 'translation_setup_error')
        raise

def get_cached_translation(text):
    """Get a cached translation if available"""
    global cache_hits, cache_misses
    
    if not redis_client:
        cache_misses += 1
        update_cache_hit_ratio(cache_hits, cache_misses)
        return None
    
    # Create a cache key based on the text
    cache_key = f"translation:{hashlib.md5(text.encode('utf-8')).hexdigest()}"
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            translation = cached.decode('utf-8')
            logging.info(f"Cache hit for text: '{text[:30]}...'")
            cache_hits += 1
            update_cache_hit_ratio(cache_hits, cache_misses)
            return translation
    except Exception as e:
        logging.error(f"Redis cache retrieval error: {str(e)}")
        record_error('translator', 'cache_retrieval_error')
    
    cache_misses += 1
    update_cache_hit_ratio(cache_hits, cache_misses)
    return None

def cache_translation(text, translation):
    """Cache a translation for future use"""
    if not redis_client:
        return
    
    # Create a cache key based on the text
    cache_key = f"translation:{hashlib.md5(text.encode('utf-8')).hexdigest()}"
    
    try:
        redis_client.set(cache_key, translation, ex=CACHE_EXPIRY)
        logging.info(f"Cached translation for text: '{text[:30]}...'")
    except Exception as e:
        logging.error(f"Redis cache storage error: {str(e)}")
        record_error('translator', 'cache_storage_error')

def perform_translation(text):
    """Translate text from English to Persian using Argostranslate"""
    # First check if we have a cached version
    cached_translation = get_cached_translation(text)
    if cached_translation:
        return cached_translation
    
    # Track memory usage before translation
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        mem_before = process.memory_info().rss
        memory_usage.labels(service='translator').set(mem_before)
        
    # No cache hit, perform the translation
    logging.info("Cache miss, performing translation...")
    
    # Use a Timer to measure translation duration
    with Timer(translation_duration):
        installed_languages = translate.get_installed_languages()
        translation_en_fa = installed_languages[0].get_translation(installed_languages[1])
        translation = translation_en_fa.translate(text)
    
    # Track memory usage after translation
    if PSUTIL_AVAILABLE:
        mem_after = process.memory_info().rss
        memory_usage.labels(service='translator').set(mem_after)
        logging.info(f"Memory usage for translation: {(mem_after-mem_before)/1024/1024:.2f}MB")
    
    # Cache the result for future use
    cache_translation(text, translation)
    
    return translation

def callback(ch, method, properties, body):
    """Handle incoming TranscriptionGenerated events"""
    try:
        # Record translation request
        record_translation_request()
        
        # Handle compressed messages
        content_encoding = properties.content_encoding if properties else None
        if content_encoding and 'zlib+base64' in content_encoding:
            body_str = decompress_message(body.decode('ascii'), content_encoding)
            message = json.loads(body_str)
            logging.info("Received compressed message")
        else:
        message = json.loads(body)
        
        if message['event_type'] != 'TranscriptionGenerated':
            return
        
        file_id = message['file_id']
        text = message['text']
        
        logging.info(f"Received TranscriptionGenerated event for file_id: {file_id}")
        
        # Get message priority if available
        message_priority = properties.priority if properties and hasattr(properties, 'priority') else None
        
        # Check if we have a valid transcription to translate
        if not text or text in ["No speech detected", "Audio processing failed due to technical issues"]:
            logging.warning(f"Received invalid or empty transcription: '{text}'")
            record_error('translator', 'invalid_transcription')
            # Update task with the error message
            task = AudioProcessingTask.objects.get(file_id=file_id)
            task.status = 'completed'
            task.translation = f"خطا در پردازش صوت: {text}" if text else "خطا در پردازش صوت: متن خالی"
            task.save()
            logging.info(f"Updated task with error message for file_id: {file_id}")
            return
        
        # Update task status
        task = AudioProcessingTask.objects.get(file_id=file_id)
        task.status = 'translating'
        task.save()
        
        # Perform translation with caching
        logging.info("Starting translation...")
        translation = perform_translation(text)
        logging.info("Translation completed")
        
        # Update task with translation
        task.status = 'completed'
        task.translation = translation
        task.save()
        logging.info(f"Updated task status to completed for file_id: {file_id}")
        
        # Publish TranslationCompleted event
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
        )
        channel = connection.channel()
        
        result_message = {
            'event_type': 'TranslationCompleted',
            'file_id': file_id,
            'translation': translation
        }
        
        # Serialize and potentially compress the message
        message_json = json.dumps(result_message)
        message_data, is_compressed = compress_message(message_json)
        
        # Set message properties
        message_props = {
            'delivery_mode': 2,  # Make message persistent
        }
        
        # Preserve original message priority
        if message_priority:
            message_props['priority'] = message_priority
            
        if is_compressed:
            message_props['content_encoding'] = 'zlib+base64'
            logging.info(f"Message compressed: {len(message_json)} -> {len(message_data)} bytes")
        
        publish_properties = pika.BasicProperties(**message_props)
        
        channel.basic_publish(
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key='',
            body=message_data,
            properties=publish_properties
        )
        connection.close()
        logging.info(f"Published TranslationCompleted event for file_id: {file_id}" +
                   (" (compressed)" if is_compressed else ""))
        
    except Exception as e:
        logging.error(f"Error in callback: {str(e)}")
        record_error('translator', 'callback_error')
        # Try to update the task with an error message
        try:
            if 'file_id' in locals():
                task = AudioProcessingTask.objects.get(file_id=file_id)
                task.status = 'completed'
                task.translation = "خطا در ترجمه: مشکل فنی رخ داده است"
                task.save()
                logging.info(f"Updated task with error message for file_id: {file_id}")
        except Exception as inner_e:
            logging.error(f"Error updating task with error status: {str(inner_e)}")
            record_error('translator', 'task_update_error')

def get_rabbitmq_connection():
    retries = 5
    delay = 2
    
    for attempt in range(retries):
        try:
            print(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{retries})...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
            )
            print("Successfully connected to RabbitMQ!")
            return connection
        except pika.exceptions.AMQPConnectionError:
            if attempt < retries - 1:
                print(f"Connection failed. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("\nError: Could not connect to RabbitMQ after multiple attempts.")
                print("Please ensure that:")
                print("1. RabbitMQ server is installed")
                print("2. RabbitMQ service is running")
                print("3. RabbitMQ is accessible at localhost:5672")
                record_error('translator', 'rabbitmq_connection_failed')
                raise

def check_health():
    """Periodically check service health"""
    while True:
        try:
            # Check RabbitMQ connection
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=settings.RABBITMQ_HOST,
                    port=settings.RABBITMQ_PORT,
                    connection_attempts=1
                )
            )
            connection.close()
            logging.info("Health check: RabbitMQ connection OK")
            
            # Check translation setup
            installed_languages = translate.get_installed_languages()
            translation_pair = next(
                (lang for lang in installed_languages if lang.code == "en"),
                None
            )
            if not translation_pair:
                logging.warning("Health check: English-Persian translation model not found")
                record_error('translator', 'health_check_model_error')
            else:
                logging.info("Health check: Translation model OK")
            
            # Check Redis if enabled
            if redis_client:
                try:
                    redis_client.ping()
                    logging.info("Health check: Redis cache OK")
                except Exception as e:
                    logging.warning(f"Health check: Redis cache error: {str(e)}")
                    record_error('translator', 'health_check_redis_error')
                
        except Exception as e:
            logging.error(f"Health check failed: {str(e)}")
            record_error('translator', 'health_check_error')
        
        time.sleep(300)  # Check every 5 minutes

def main():
    try:
        # Set service name for metrics
        os.environ['SERVICE_NAME'] = 'translator'
        
        # Start metrics collection
        from asr_translator.metrics import start_metrics_collection
        metrics_thread = start_metrics_collection()
        
        # Set CPU affinity for better performance
        set_cpu_affinity()
        
        # Setup translation
        setup_translation()
        
        # Start health check in background thread
        health_thread = threading.Thread(target=check_health, daemon=True)
        health_thread.start()
        
        # Get connection with retry logic
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Setup channel - declare exchange
        channel.exchange_declare(exchange=settings.RABBITMQ_EXCHANGE, exchange_type='fanout')
        
        # Declare queue with priority support
        result = channel.queue_declare(
            queue='translation_queue',  # Named queue for better visibility
            durable=True,  # Survive broker restarts
            arguments={
                'x-max-priority': 10  # Enable priority from 1-10
            }
        )
        queue_name = result.method.queue
        
        # Bind queue to the exchange
        channel.queue_bind(exchange=settings.RABBITMQ_EXCHANGE, queue=queue_name)
        
        logging.info("Translation Service is running. Waiting for transcriptions...")
        # Process higher priority messages first
        channel.basic_qos(prefetch_count=1)  # Only take one message at a time
        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        channel.start_consuming()
    except KeyboardInterrupt:
        logging.info("Shutting down Translation service...")
        if 'connection' in locals():
            try:
                connection.close()
            except:
                pass
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        record_error('translator', 'fatal_error')
        raise

if __name__ == '__main__':
    main()