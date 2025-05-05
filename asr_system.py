import os
import json
import pika
import django
import time
import logging
import threading
import concurrent.futures
import tempfile
import subprocess
from vosk import Model, KaldiRecognizer
import wave

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, CPU affinity settings will be disabled")

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

# Constants for processing
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
MAX_WORKERS = 4  # Maximum number of parallel workers
SEGMENT_DURATION = 30  # Segment duration in seconds for parallel processing
CPU_AFFINITY_ENABLED = os.environ.get('CPU_AFFINITY_ENABLED', 'True').lower() in ('true', '1', 't')

# Global model cache
global_model = None
model_lock = threading.Lock()

def set_cpu_affinity():
    """Set CPU affinity for the ASR service if psutil is available"""
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
        
        # For ASR service, use the first half of available cores (rounded up)
        # This leaves the second half for other services
        cores_to_use = list(range(0, (cpu_count + 1) // 2))
        
        # Set affinity
        process.cpu_affinity(cores_to_use)
        logging.info(f"Set CPU affinity to cores: {cores_to_use}")
    except Exception as e:
        logging.error(f"Error setting CPU affinity: {str(e)}")

def get_model(model_path="vosk-model-small-en-us-0.15"):
    """Get the ASR model, using a cached version if available"""
    global global_model
    
    # If the model is already loaded, return it
    if global_model is not None:
        return global_model
    
    # Use a lock to prevent multiple threads from loading the model simultaneously
    with model_lock:
        # Check again in case another thread loaded the model while we were waiting
        if global_model is not None:
            return global_model
            
        # Check if model exists
        if not os.path.exists(model_path):
            logging.error(f"VOSK model not found at {model_path}")
            raise FileNotFoundError(f"VOSK model not found at {model_path}")
        
        logging.info(f"Loading VOSK model from {model_path} (initial load)")
        global_model = Model(model_path)
        logging.info("Model loaded successfully and cached globally")
        
        return global_model

def split_audio_file(file_path, segment_duration=SEGMENT_DURATION):
    """Split a large audio file into smaller segments for parallel processing"""
    logging.info(f"Splitting large audio file: {file_path}")
    
    try:
        # Get file info
        with wave.open(file_path, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / framerate
        
        logging.info(f"Audio file details: duration={duration:.2f}s, framerate={framerate}Hz, channels={channels}")
        
        # If file is small enough, don't split
        if duration <= segment_duration:
            logging.info("File is small enough to process as a single unit")
            return [file_path]
        
        # Calculate number of segments
        n_segments = int(duration / segment_duration) + (1 if duration % segment_duration > 0 else 0)
        logging.info(f"Splitting into {n_segments} segments")
        
        # Extract filename without extension
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create temp directory for segments
        temp_dir = tempfile.mkdtemp(prefix="asr_segments_")
        segment_paths = []
        
        # Use ffmpeg to split the file
        for i in range(n_segments):
            start_time = i * segment_duration
            output_file = os.path.join(temp_dir, f"{base_name}_segment_{i}.wav")
            
            # Use ffmpeg to extract segment
            cmd = [
                "ffmpeg",
                "-i", file_path,
                "-ss", str(start_time),
                "-t", str(segment_duration),
                "-acodec", "pcm_s16le",
                "-ar", str(framerate),
                "-ac", str(channels),
                output_file,
                "-y",  # Overwrite output file if it exists
                "-loglevel", "error"  # Suppress ffmpeg output
            ]
            
            subprocess.run(cmd, check=True)
            segment_paths.append(output_file)
            logging.info(f"Created segment {i+1}/{n_segments}: {output_file}")
        
        return segment_paths
    
    except Exception as e:
        logging.error(f"Error splitting audio file: {str(e)}")
        return [file_path]  # Fall back to original file

def combine_transcription_results(results):
    """Combine transcription results from multiple segments"""
    combined = " ".join(filter(None, [r.strip() for r in results]))
    return combined if combined else "No speech detected"

def process_audio_segment(segment_path, model_path):
    """Process a single audio segment - to be used in parallel processing"""
    try:
        # Use the global model cache
        model = get_model(model_path)
        wf = wave.open(segment_path, "rb")
        sample_rate = wf.getframerate()
        
        recognizer = KaldiRecognizer(model, sample_rate)
        recognizer.SetWords(True)
        
        text = ""
        
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if "text" in result and result["text"].strip():
                    text += result["text"] + " "
        
        final_result = json.loads(recognizer.FinalResult())
        if "text" in final_result and final_result["text"].strip():
            text += final_result["text"]
        
        return text.strip()
    
    except Exception as e:
        logging.error(f"Error processing segment {segment_path}: {str(e)}")
        return ""

def process_audio_parallel(file_path):
    """Process audio file in parallel for larger files"""
    model_path = "vosk-model-small-en-us-0.15"
    
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        
        # For smaller files, use the standard processing
        if file_size < LARGE_FILE_THRESHOLD:
            logging.info(f"File size ({file_size} bytes) below threshold, using standard processing")
            return process_audio(file_path)
        
        logging.info(f"Large file detected ({file_size} bytes), using parallel processing")
        
        # Split file into segments
        segment_paths = split_audio_file(file_path)
        
        if len(segment_paths) == 1:
            logging.info("Only one segment created, using standard processing")
            return process_audio(file_path)
        
        # Process segments in parallel
        logging.info(f"Processing {len(segment_paths)} segments in parallel with {MAX_WORKERS} workers")
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_segment = {
                executor.submit(process_audio_segment, segment, model_path): segment 
                for segment in segment_paths
            }
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_segment)):
                segment = future_to_segment[future]
                try:
                    result = future.result()
                    logging.info(f"Completed segment {i+1}/{len(segment_paths)}: {os.path.basename(segment)}")
                    results.append(result)
                except Exception as e:
                    logging.error(f"Error processing segment {segment}: {str(e)}")
        
        # Combine results
        combined_text = combine_transcription_results(results)
        logging.info(f"Combined transcription from {len(segment_paths)} segments: {combined_text[:100]}...")
        
        # Clean up temporary files if they were created
        if segment_paths[0] != file_path:
            for segment in segment_paths:
                try:
                    os.remove(segment)
                except:
                    pass
            try:
                os.rmdir(os.path.dirname(segment_paths[0]))
            except:
                pass
        
        return combined_text
        
    except Exception as e:
        logging.error(f"Error in parallel processing: {str(e)}")
        # Fall back to standard processing
        logging.info("Falling back to standard processing")
        return process_audio(file_path)

def process_audio(file_path):
    """Perform ASR on the audio file using VOSK with streaming for faster processing"""
    model_path = "vosk-model-small-en-us-0.15"
    
    try:
        # Use the global model cache instead of loading it each time
        model = get_model(model_path)
        wf = wave.open(file_path, "rb")
        
        # Get the sample rate from the file
        sample_rate = wf.getframerate()
        logging.info(f"Audio file sample rate: {sample_rate} Hz")
        
        # VOSK works best with 16kHz audio
        if sample_rate != 16000:
            logging.warning(f"Audio sample rate is {sample_rate}Hz, but VOSK works best with 16000Hz")
            # We'll try with the original sample rate anyway, and rely on exception handling
        
        # Create recognizer with SetWords to get word timings
        recognizer = KaldiRecognizer(model, sample_rate)
        recognizer.SetWords(True)
        
        logging.info(f"Processing audio file: {file_path}")
        text = ""
        
        # Process frames
        try:
            # Define chunk size for processing - smaller for more responsive streaming
            chunk_size = 4000  # Adjust based on performance testing
            
            # Process in chunks and collect results
            chunk_results = []
            chunk_count = 0
            current_text = ""
            
            while True:
                data = wf.readframes(chunk_size)
                if len(data) == 0:
                    break
                
                chunk_count += 1
                try:
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if "text" in result and result["text"].strip():
                            current_text = result["text"]
                            chunk_results.append(current_text)
                            logging.info(f"Chunk {chunk_count} processed: '{current_text}'")
                            text += current_text + " "
                except Exception as e:
                    logging.error(f"Error processing frame {chunk_count}: {str(e)}")
                    continue
            
            # Get final result for any remaining audio
            final_result = json.loads(recognizer.FinalResult())
            if "text" in final_result and final_result["text"].strip():
                final_text = final_result["text"]
                chunk_results.append(final_text)
                text += final_text
                logging.info(f"Final chunk processed: '{final_text}'")
                
            if not text.strip():
                logging.warning("No transcription generated, audio might be silent or unrecognizable")
                text = "No speech detected"
                
            logging.info("Audio processing completed successfully")
            logging.info(f"Full transcription: {text.strip()}")
            return text.strip()
            
        except Exception as e:
            logging.error(f"Error during frame processing: {str(e)}")
            # Fallback: return a message that we couldn't process the audio
            return "Audio processing failed due to technical issues"
        
    except FileNotFoundError as e:
        logging.error(f"Model not found error: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error processing audio file: {str(e)}")
        # Don't raise the exception, return a fallback message instead
        return "Audio processing failed due to technical issues"

def callback(ch, method, properties, body):
    """Handle incoming AudioFileUploaded events"""
    try:
        message = json.loads(body)
        
        if message['event_type'] != 'AudioFileUploaded':
            return
        
        file_id = message['file_id']
        file_path = message['file_path']
        
        logging.info(f"Received AudioFileUploaded event for file_id: {file_id}")
        # Get message priority if available
        message_priority = properties.priority if properties and hasattr(properties, 'priority') else None
        logging.info(f"Message priority: {message_priority}")
        
        # Update task status
        task = AudioProcessingTask.objects.get(file_id=file_id)
        task.status = 'transcribing'
        task.save()
        
        # Perform ASR - Use parallel processing for large files
        text = process_audio_parallel(file_path)
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
        
        # Preserve original message priority
        publish_properties = None
        if message_priority:
            publish_properties = pika.BasicProperties(priority=message_priority)
        
        channel.basic_publish(
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key='',
            body=json.dumps(message),
            properties=publish_properties
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
            
            # Check VOSK model - use get_model to check the cached model
            try:
                model = get_model()
                logging.info("Health check: VOSK model OK (cached)")
            except Exception as e:
                logging.warning(f"Health check: VOSK model issue: {str(e)}")
                
        except Exception as e:
            logging.error(f"Health check failed: {str(e)}")
        
        time.sleep(300)  # Check every 5 minutes

def main():
    try:
        # Set CPU affinity for better performance
        set_cpu_affinity()
        
        # Preload the model at startup
        try:
            get_model()
            print("VOSK model preloaded successfully!")
        except Exception as e:
            print(f"Warning: Failed to preload VOSK model: {str(e)}")
        
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
            queue='asr_processing_queue',  # Named queue for better visibility
            durable=True,  # Survive broker restarts
            arguments={
                'x-max-priority': 10  # Enable priority from 1-10
            }
        )
        queue_name = result.method.queue
        
        # Bind queue to the exchange
        channel.queue_bind(exchange=settings.RABBITMQ_EXCHANGE, queue=queue_name)
        
        print("ASR Service is running. Waiting for audio files...")
        # Process higher priority messages first
        channel.basic_qos(prefetch_count=1)  # Only take one message at a time
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