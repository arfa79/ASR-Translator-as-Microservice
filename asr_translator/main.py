"""
Main entry point for the ASR-Translator system.
Initializes all components including metrics and autoscaling.
"""

import os
import logging
import signal
import sys
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Main] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Check for optional dependencies
METRICS_AVAILABLE = False
AUTOSCALER_AVAILABLE = False

try:
    from asr_translator.metrics import start_metrics_collection
    METRICS_AVAILABLE = True
except ImportError:
    logging.warning("Metrics module not available. Performance monitoring disabled.")

try:
    from asr_translator.autoscaler import start_autoscaler, PROMETHEUS_AVAILABLE
    AUTOSCALER_AVAILABLE = True
except ImportError:
    logging.warning("Autoscaler module not available. Autoscaling disabled.")

# Global flags for threads
shutdown_requested = False
threads = []

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logging.info("Shutdown signal received, stopping services...")
    shutdown_requested = True

def main():
    """Main function to start the ASR-Translator system"""
    global threads
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start metrics collection if available
        if METRICS_AVAILABLE:
            logging.info("Starting metrics collection...")
            metrics_thread = start_metrics_collection()
            threads.append(metrics_thread)
        else:
            logging.warning("Metrics collection not available. Skipping.")
        
        # Check environment to see if autoscaling is enabled
        autoscaling_enabled = os.environ.get('ENABLE_AUTOSCALING', 'False').lower() in ('true', '1', 't')
        
        if autoscaling_enabled and AUTOSCALER_AVAILABLE:
            if not PROMETHEUS_AVAILABLE:
                logging.warning("Autoscaling enabled but Prometheus client not available.")
                logging.warning("Install with 'pip install prometheus_client requests' to enable autoscaling.")
            else:
                # Start autoscaler
                logging.info("Starting autoscaler...")
                autoscaler_thread = start_autoscaler()
                threads.append(autoscaler_thread)
        else:
            if not AUTOSCALER_AVAILABLE:
                logging.warning("Autoscaling module not available.")
            else:
                logging.info("Autoscaling is disabled. Set ENABLE_AUTOSCALING=True to enable it.")
        
        # Monitor threads and keep the main process running
        while not shutdown_requested:
            # Check if threads are alive
            for thread in list(threads):
                if not thread.is_alive():
                    logging.warning(f"Thread {thread.name} died, removing from monitoring")
                    threads.remove(thread)
                    
            time.sleep(10)
            
    except Exception as e:
        logging.error(f"Error in main process: {str(e)}")
        return 1
    finally:
        logging.info("ASR-Translator system shutting down...")
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 