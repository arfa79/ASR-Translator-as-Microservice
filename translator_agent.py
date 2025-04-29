import os
import json
import pika
import django
import time
import logging
import threading
from argostranslate import package, translate

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
            raise RuntimeError(
                "English to Persian translation package not found. "
                "Please check your internet connection and try again."
            )
        
        logging.info("Installing English to Persian translation package...")
        package.install_from_path(package_to_install.download())
        logging.info("Translation setup completed successfully")
        
    except Exception as e:
        logging.error(f"Error setting up translation: {str(e)}")
        raise

def callback(ch, method, properties, body):
    """Handle incoming TranscriptionGenerated events"""
    try:
        message = json.loads(body)
        
        if message['event_type'] != 'TranscriptionGenerated':
            return
        
        file_id = message['file_id']
        text = message['text']
        
        logging.info(f"Received TranscriptionGenerated event for file_id: {file_id}")
        
        # Update task status
        task = AudioProcessingTask.objects.get(file_id=file_id)
        task.status = 'translating'
        task.save()
        
        # Perform translation
        logging.info("Starting translation...")
        installed_languages = translate.get_installed_languages()
        translation_en_fa = installed_languages[0].get_translation(installed_languages[1])
        translation = translation_en_fa.translate(text)
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
        
        message = {
            'event_type': 'TranslationCompleted',
            'file_id': file_id,
            'translation': translation
        }
        
        channel.basic_publish(
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key='',
            body=json.dumps(message)
        )
        connection.close()
        logging.info(f"Published TranslationCompleted event for file_id: {file_id}")
        
    except Exception as e:
        logging.error(f"Error in callback: {str(e)}")
        raise

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
            else:
                logging.info("Health check: Translation model OK")
                
        except Exception as e:
            logging.error(f"Health check failed: {str(e)}")
        
        time.sleep(300)  # Check every 5 minutes

def main():
    try:
        # Setup translation
        setup_translation()
        
        # Start health check in background thread
        health_thread = threading.Thread(target=check_health, daemon=True)
        health_thread.start()
        
        # Get connection with retry logic
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Setup channel
        channel.exchange_declare(exchange=settings.RABBITMQ_EXCHANGE, exchange_type='fanout')
        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange=settings.RABBITMQ_EXCHANGE, queue=queue_name)
        
        logging.info("Translation Service is running. Waiting for transcriptions...")
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
        raise

if __name__ == '__main__':
    main()