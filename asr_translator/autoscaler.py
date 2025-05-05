"""
Autoscaler for ASR-Translator microservices.
This module monitors system metrics and dynamically scales services up or down.
"""

import os
import time
import logging
import threading
import subprocess
import json
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Autoscaler] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Try to import optional dependencies
PROMETHEUS_AVAILABLE = False
try:
    import requests
    from prometheus_client.parser import text_string_to_metric_families
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logging.warning("Prometheus client or requests not available. "
                   "Install with 'pip install prometheus_client requests' for autoscaling to work.")

# Configuration
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
CHECK_INTERVAL = int(os.environ.get('AUTOSCALE_CHECK_INTERVAL', 30))  # seconds
MAX_ASR_INSTANCES = int(os.environ.get('MAX_ASR_INSTANCES', 5))
MAX_TRANSLATOR_INSTANCES = int(os.environ.get('MAX_TRANSLATOR_INSTANCES', 5))
MIN_INSTANCES = int(os.environ.get('MIN_INSTANCES', 1))

# Thresholds
QUEUE_HIGH_THRESHOLD = int(os.environ.get('QUEUE_HIGH_THRESHOLD', 10))
QUEUE_LOW_THRESHOLD = int(os.environ.get('QUEUE_LOW_THRESHOLD', 2))
CPU_HIGH_THRESHOLD = float(os.environ.get('CPU_HIGH_THRESHOLD', 70.0))  # percentage
CPU_LOW_THRESHOLD = float(os.environ.get('CPU_LOW_THRESHOLD', 20.0))  # percentage
PROCESSING_TIME_THRESHOLD = float(os.environ.get('PROCESSING_TIME_THRESHOLD', 30.0))  # seconds

# Current state
asr_instances = 1
translator_instances = 1
scaling_lock = threading.Lock()

class PrometheusClient:
    """Client for querying Prometheus metrics"""
    
    @staticmethod
    def query(query):
        """Execute a Prometheus query"""
        if not PROMETHEUS_AVAILABLE:
            logging.error("Prometheus client not available")
            return None
            
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            
            if response.status_code != 200:
                logging.error(f"Prometheus query failed: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            
            if result["status"] != "success" or not result["data"]["result"]:
                logging.warning(f"No results for query: {query}")
                return None
                
            return result["data"]["result"][0]["value"][1]
        except Exception as e:
            logging.error(f"Error querying Prometheus: {str(e)}")
            return None
            
    @staticmethod
    def get_metric_direct(metric_url):
        """Get metrics directly from an exporter endpoint"""
        if not PROMETHEUS_AVAILABLE:
            logging.error("Prometheus client not available")
            return {}
            
        try:
            response = requests.get(metric_url)
            
            if response.status_code != 200:
                logging.error(f"Failed to get metrics from {metric_url}: {response.status_code}")
                return {}
                
            metrics = {}
            for family in text_string_to_metric_families(response.text):
                for sample in family.samples:
                    metrics[sample.name] = sample.value
                    
            return metrics
        except Exception as e:
            logging.error(f"Error getting metrics from {metric_url}: {str(e)}")
            return {}

def get_scaling_metrics():
    """Get metrics relevant for scaling decisions"""
    client = PrometheusClient()
    
    # Queue sizes
    asr_queue_size = client.query("rabbitmq_queue_size{queue_name='asr_processing_queue'}")
    translation_queue_size = client.query("rabbitmq_queue_size{queue_name='translation_queue'}")
    
    # CPU usage
    asr_cpu = client.query("avg(cpu_usage_percent{service='asr'})")
    translator_cpu = client.query("avg(cpu_usage_percent{service='translator'})")
    
    # Processing times (95th percentile)
    asr_time = client.query("histogram_quantile(0.95, sum(rate(asr_processing_duration_seconds_bucket[5m])) by (le))")
    translation_time = client.query("histogram_quantile(0.95, sum(rate(translation_duration_seconds_bucket[5m])) by (le))")
    
    # Convert to float or set to None if not available
    metrics = {
        "asr_queue_size": float(asr_queue_size) if asr_queue_size else None,
        "translation_queue_size": float(translation_queue_size) if translation_queue_size else None,
        "asr_cpu": float(asr_cpu) if asr_cpu else None,
        "translator_cpu": float(translator_cpu) if translator_cpu else None,
        "asr_time": float(asr_time) if asr_time else None,
        "translation_time": float(translation_time) if translation_time else None
    }
    
    logging.info(f"Current metrics: {json.dumps(metrics, indent=2)}")
    return metrics

def scale_asr_service(target_instances):
    """Scale the ASR service to the target number of instances"""
    global asr_instances
    
    with scaling_lock:
        current = asr_instances
        if current == target_instances:
            return
            
        if target_instances > current:
            logging.info(f"Scaling up ASR service from {current} to {target_instances} instances")
            # Launch new instances
            for i in range(current, target_instances):
                instance_id = i + 1
                try:
                    # Example using Docker
                    cmd = [
                        "docker", "run", "-d",
                        "--name", f"asr-service-{instance_id}",
                        "--network", "host",
                        "-e", f"METRICS_PORT={8010 + instance_id}",
                        "-e", "CPU_AFFINITY_ENABLED=True",
                        "-v", "./vosk-model-small-en-us-0.15:/vosk-model-small-en-us-0.15",
                        "asr-translator/asr-service"
                    ]
                    subprocess.run(cmd, check=True)
                    logging.info(f"Started ASR instance {instance_id}")
                except Exception as e:
                    logging.error(f"Failed to start ASR instance {instance_id}: {str(e)}")
                    return
        else:
            logging.info(f"Scaling down ASR service from {current} to {target_instances} instances")
            # Remove instances
            for i in range(target_instances, current):
                instance_id = i + 1
                try:
                    # Example using Docker
                    cmd = ["docker", "stop", f"asr-service-{instance_id}"]
                    subprocess.run(cmd, check=True)
                    cmd = ["docker", "rm", f"asr-service-{instance_id}"]
                    subprocess.run(cmd, check=True)
                    logging.info(f"Stopped ASR instance {instance_id}")
                except Exception as e:
                    logging.error(f"Failed to stop ASR instance {instance_id}: {str(e)}")
                    return
                    
        # Update current state
        asr_instances = target_instances
        logging.info(f"ASR service scaled to {target_instances} instances")

def scale_translator_service(target_instances):
    """Scale the Translator service to the target number of instances"""
    global translator_instances
    
    with scaling_lock:
        current = translator_instances
        if current == target_instances:
            return
            
        if target_instances > current:
            logging.info(f"Scaling up Translator service from {current} to {target_instances} instances")
            # Launch new instances
            for i in range(current, target_instances):
                instance_id = i + 1
                try:
                    # Example using Docker
                    cmd = [
                        "docker", "run", "-d",
                        "--name", f"translator-service-{instance_id}",
                        "--network", "host",
                        "-e", f"METRICS_PORT={8020 + instance_id}",
                        "-e", "CPU_AFFINITY_ENABLED=True",
                        "asr-translator/translator-service"
                    ]
                    subprocess.run(cmd, check=True)
                    logging.info(f"Started Translator instance {instance_id}")
                except Exception as e:
                    logging.error(f"Failed to start Translator instance {instance_id}: {str(e)}")
                    return
        else:
            logging.info(f"Scaling down Translator service from {current} to {target_instances} instances")
            # Remove instances
            for i in range(target_instances, current):
                instance_id = i + 1
                try:
                    # Example using Docker
                    cmd = ["docker", "stop", f"translator-service-{instance_id}"]
                    subprocess.run(cmd, check=True)
                    cmd = ["docker", "rm", f"translator-service-{instance_id}"]
                    subprocess.run(cmd, check=True)
                    logging.info(f"Stopped Translator instance {instance_id}")
                except Exception as e:
                    logging.error(f"Failed to stop Translator instance {instance_id}: {str(e)}")
                    return
                    
        # Update current state
        translator_instances = target_instances
        logging.info(f"Translator service scaled to {target_instances} instances")

def autoscale_check():
    """Check metrics and determine if scaling is needed"""
    if not PROMETHEUS_AVAILABLE:
        logging.warning("Autoscaling disabled: Prometheus client not available")
        return
        
    metrics = get_scaling_metrics()
    
    # Handle missing metrics gracefully
    if not metrics or all(v is None for v in metrics.values()):
        logging.warning("No metrics available for scaling decision")
        return
    
    # Default to current instances if metrics are missing
    target_asr_instances = asr_instances
    target_translator_instances = translator_instances
    
    # Scale ASR service based on queue size, CPU usage and processing time
    if metrics["asr_queue_size"] and metrics["asr_queue_size"] > QUEUE_HIGH_THRESHOLD:
        target_asr_instances = min(asr_instances + 1, MAX_ASR_INSTANCES)
        logging.info(f"ASR queue size ({metrics['asr_queue_size']}) exceeds threshold, scaling up")
    elif metrics["asr_cpu"] and metrics["asr_cpu"] > CPU_HIGH_THRESHOLD:
        target_asr_instances = min(asr_instances + 1, MAX_ASR_INSTANCES)
        logging.info(f"ASR CPU usage ({metrics['asr_cpu']}%) exceeds threshold, scaling up")
    elif metrics["asr_time"] and metrics["asr_time"] > PROCESSING_TIME_THRESHOLD:
        target_asr_instances = min(asr_instances + 1, MAX_ASR_INSTANCES)
        logging.info(f"ASR processing time ({metrics['asr_time']}s) exceeds threshold, scaling up")
    elif (metrics["asr_queue_size"] and metrics["asr_queue_size"] < QUEUE_LOW_THRESHOLD and
          (not metrics["asr_cpu"] or metrics["asr_cpu"] < CPU_LOW_THRESHOLD)):
        target_asr_instances = max(asr_instances - 1, MIN_INSTANCES)
        logging.info(f"ASR load is low, scaling down")
    
    # Scale Translator service
    if metrics["translation_queue_size"] and metrics["translation_queue_size"] > QUEUE_HIGH_THRESHOLD:
        target_translator_instances = min(translator_instances + 1, MAX_TRANSLATOR_INSTANCES)
        logging.info(f"Translator queue size ({metrics['translation_queue_size']}) exceeds threshold, scaling up")
    elif metrics["translator_cpu"] and metrics["translator_cpu"] > CPU_HIGH_THRESHOLD:
        target_translator_instances = min(translator_instances + 1, MAX_TRANSLATOR_INSTANCES)
        logging.info(f"Translator CPU usage ({metrics['translator_cpu']}%) exceeds threshold, scaling up")
    elif metrics["translation_time"] and metrics["translation_time"] > PROCESSING_TIME_THRESHOLD:
        target_translator_instances = min(translator_instances + 1, MAX_TRANSLATOR_INSTANCES)
        logging.info(f"Translation time ({metrics['translation_time']}s) exceeds threshold, scaling up")
    elif (metrics["translation_queue_size"] and metrics["translation_queue_size"] < QUEUE_LOW_THRESHOLD and
          (not metrics["translator_cpu"] or metrics["translator_cpu"] < CPU_LOW_THRESHOLD)):
        target_translator_instances = max(translator_instances - 1, MIN_INSTANCES)
        logging.info(f"Translator load is low, scaling down")
    
    # Execute scaling if needed
    if target_asr_instances != asr_instances:
        scale_asr_service(target_asr_instances)
        
    if target_translator_instances != translator_instances:
        scale_translator_service(target_translator_instances)

def autoscaler_loop():
    """Main autoscaler loop - runs continuously checking metrics and scaling"""
    logging.info("Autoscaler started")
    
    while True:
        try:
            autoscale_check()
        except Exception as e:
            logging.error(f"Error in autoscale check: {str(e)}")
            
        time.sleep(CHECK_INTERVAL)

def start_autoscaler():
    """Start the autoscaler in a background thread"""
    if not PROMETHEUS_AVAILABLE:
        logging.warning("Autoscaler disabled due to missing dependencies.")
        logging.warning("Install with 'pip install prometheus_client requests' to enable autoscaling.")
        # Return a dummy thread that's already dead so the health check will report correctly
        dummy_thread = threading.Thread(target=lambda: None)
        dummy_thread.name = "autoscaler-disabled"
        return dummy_thread
        
    autoscaler_thread = threading.Thread(target=autoscaler_loop, daemon=True)
    autoscaler_thread.name = "autoscaler"
    autoscaler_thread.start()
    logging.info(f"Autoscaler started with check interval of {CHECK_INTERVAL} seconds")
    return autoscaler_thread

if __name__ == "__main__":
    # Start the autoscaler when run directly
    try:
        if not PROMETHEUS_AVAILABLE:
            logging.error("Cannot start autoscaler: required dependencies missing.")
            logging.error("Install with 'pip install prometheus_client requests'")
            sys.exit(1)
            
        logging.info("Starting autoscaler...")
        autoscaler_thread = start_autoscaler()
        
        # Keep the main thread running
        while True:
            time.sleep(60)
            if not autoscaler_thread.is_alive():
                logging.error("Autoscaler thread died, restarting...")
                autoscaler_thread = start_autoscaler()
                
    except KeyboardInterrupt:
        logging.info("Autoscaler shutting down...") 