import os
import json
import pika
import django
from vosk import Model, KaldiRecognizer
import wave

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asr_translator.settings')
django.setup()

from django.conf import settings
from audio_processing.models import AudioProcessingTask

def process_audio(file_path):
    """Perform ASR on the audio file using VOSK"""
    # Load VOSK model (you need to download this separately)
    model = Model("vosk-model-en-us-0.22")
    
    wf = wave.open(file_path, "rb")
    recognizer = KaldiRecognizer(model, wf.getframerate())
    
    text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if recognizer.AcceptWaveform(data):
            text += json.loads(recognizer.Result())["text"] + " "
    
    text += json.loads(recognizer.FinalResult())["text"]
    return text.strip()

def callback(ch, method, properties, body):
    """Handle incoming AudioFileUploaded events"""
    message = json.loads(body)
    
    if message['event_type'] != 'AudioFileUploaded':
        return
    
    file_id = message['file_id']
    file_path = message['file_path']
    
    # Update task status
    task = AudioProcessingTask.objects.get(file_id=file_id)
    task.status = 'transcribing'
    task.save()
    
    # Perform ASR
    text = process_audio(file_path)
    
    # Publish TranscriptionGenerated event
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    )
    channel = connection.channel()
    
    message = {
        'event_type': 'TranscriptionGenerated',
        'file_id': file_id,
        'text': text
    }
    
    channel.basic_publish(
        exchange=settings.RABBITMQ_EXCHANGE,
        routing_key='',
        body=json.dumps(message)
    )
    connection.close()

def main():
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
    
    print("ASR Service is running. Waiting for audio files...")
    channel.start_consuming()

if __name__ == '__main__':
    main()