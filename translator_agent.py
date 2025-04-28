import os
import json
import pika
import django
from argostranslate import package, translate

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asr_translator.settings')
django.setup()

from django.conf import settings
from audio_processing.models import AudioProcessingTask

def setup_translation():
    """Setup Argostranslate with English to Persian translation"""
    # Download and install translation package if not already installed
    package.update_package_index()
    available_packages = package.get_available_packages()
    package_to_install = next(
        (pkg for pkg in available_packages if pkg.from_code == "en" and pkg.to_code == "fa"),
        None
    )
    
    if package_to_install:
        package.install_from_path(package_to_install.download())

def callback(ch, method, properties, body):
    """Handle incoming TranscriptionGenerated events"""
    message = json.loads(body)
    
    if message['event_type'] != 'TranscriptionGenerated':
        return
    
    file_id = message['file_id']
    text = message['text']
    
    # Update task status
    task = AudioProcessingTask.objects.get(file_id=file_id)
    task.status = 'translating'
    task.save()
    
    # Perform translation
    installed_languages = translate.get_installed_languages()
    translation_en_fa = installed_languages[0].get_translation(installed_languages[1])
    translation = translation_en_fa.translate(text)
    
    # Update task with translation
    task.status = 'completed'
    task.translation = translation
    task.save()
    
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

def main():
    # Setup translation
    setup_translation()
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    )
    channel = connection.channel()
    
    # Declare exchange
    channel.exchange_declare(exchange=settings.RABBITMQ_EXCHANGE, exchange_type='fanout')
    
    # Create and bind queue
    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue
    channel.queue_bind(exchange=settings.RABBITMQ_EXCHANGE, queue=queue_name)
    
    # Start consuming messages
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    
    print("Translation Service is running. Waiting for transcriptions...")
    channel.start_consuming()

if __name__ == '__main__':
    main()