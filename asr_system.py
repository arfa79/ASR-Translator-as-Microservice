import os
import json
import pika
import django
import time
import logging
import threading
from vosk import Model, KaldiRecognizer
import wave

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ASR Service] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asr_translator.settings')
django.setup()

from django.conf import settings
from audio_processing.models import AudioProcessingTask

def process_audio(file_path):
    """Perform ASR on the audio file using VOSK"""
    model_path = "vosk-model-en-us-0.22"
    
    try:
        # Load VOSK model
        if not os.path.exists(model_path):
            logging.error(f"VOSK model not found at {model_path}")
            raise FileNotFoundError(
                f"VOSK model not found at {model_path}. Please download it from "
                "https://alphacephei.com/vosk/models and extract to the project directory."
            )
            
        logging.info(f"Loading VOSK model from {model_path}")
        model = Model(model_path)
        wf = wave.open(file_path, "rb")
        recognizer = KaldiRecognizer(model, wf.getframerate())
        
        logging.info(f"Processing audio file: {file_path}")
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                text += json.loads(recognizer.Result())["text"] + " "
        
        text += json.loads(recognizer.FinalResult())["text"]
        logging.info("Audio processing completed successfully")
        return text.strip()
        
    except FileNotFoundError as e:
        logging.error(f"Model not found error: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error processing audio file: {str(e)}")
        raise

def callback(ch, method, properties, body):
    """Handle incoming AudioFileUploaded events"""
    try:
        message = json.loads(body)
        
        if message['event_type'] != 'AudioFileUploaded':
            return
        
        file_id = message['file_id']
        file_path = message['file_path']
        
        logging.info(f"Received AudioFileUploaded event for file_id: {file_id}")
        
        # Update task status
        task = AudioProcessingTask.objects.get(file_id=file_id)
        task.status = 'transcribing'
        task.save()
        
        # Perform ASR
        text = process_audio(file_path)
        logging.info(f"Successfully transcribed audio for file_id: {file_id}")
        
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
        logging.info(f"Published TranscriptionGenerated event for file_id: {file_id}")
        
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
            
            # Check VOSK model
            model_path = "vosk-model-en-us-0.22"
            if not os.path.exists(model_path):
                logging.warning("Health check: VOSK model not found")
            else:
                logging.info("Health check: VOSK model OK")
                
        except Exception as e:
            logging.error(f"Health check failed: {str(e)}")
        
        time.sleep(300)  # Check every 5 minutes

def main():
    try:
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
        
        print("ASR Service is running. Waiting for audio files...")
        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nShutting down ASR service...")
        if 'connection' in locals():
            try:
                connection.close()
            except:
                pass
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    main()