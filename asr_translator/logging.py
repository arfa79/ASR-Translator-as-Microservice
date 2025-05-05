import logging
import threading
import time
from typing import Dict, Optional, Any

# Dictionary to store metrics for Prometheus to scrape
prometheus_metrics = {
    'error_count': 0,
    'error_by_type': {},
    'last_error_time': 0,
    'error_by_component': {},
}

# Lock for thread-safe access to metrics
metrics_lock = threading.Lock()


class PrometheusLogHandler(logging.Handler):
    """
    Custom log handler that updates Prometheus metrics for error tracking.
    This handler works by updating a global metrics dictionary that can be
    exposed via a Prometheus metrics endpoint.
    """
    
    def __init__(self, level=logging.NOTSET):
        """
        Initialize the handler with the given logging level.
        
        Args:
            level: The logging level for this handler
        """
        super().__init__(level)
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Update Prometheus metrics based on the log record.
        
        Args:
            record: The log record to be processed
        """
        try:
            # Update metrics in a thread-safe manner
            with metrics_lock:
                # Increment global error count
                prometheus_metrics['error_count'] += 1
                
                # Update the last error time
                prometheus_metrics['last_error_time'] = time.time()
                
                # Update error count by error type
                error_type = record.levelname
                prometheus_metrics['error_by_type'][error_type] = \
                    prometheus_metrics['error_by_type'].get(error_type, 0) + 1
                
                # Update error count by component
                component = record.name.split('.')[-1]
                if component not in prometheus_metrics['error_by_component']:
                    prometheus_metrics['error_by_component'][component] = 0
                prometheus_metrics['error_by_component'][component] += 1
                
        except Exception:
            self.handleError(record)


def get_prometheus_metrics() -> Dict[str, Any]:
    """
    Get a copy of the current Prometheus metrics.
    
    Returns:
        Dict: Copy of the current metrics dictionary
    """
    with metrics_lock:
        # Return a copy to avoid race conditions
        return prometheus_metrics.copy()


def reset_prometheus_metrics() -> None:
    """
    Reset all Prometheus metrics to their initial values.
    Used for testing or when metrics need to be reset.
    """
    with metrics_lock:
        prometheus_metrics['error_count'] = 0
        prometheus_metrics['error_by_type'] = {}
        prometheus_metrics['last_error_time'] = 0
        prometheus_metrics['error_by_component'] = {}


def increment_counter(metric_name: str, labels: Optional[Dict[str, str]] = None) -> None:
    """
    Increment a custom counter metric.
    
    Args:
        metric_name: Name of the counter to increment
        labels: Optional labels for the counter
    """
    with metrics_lock:
        if metric_name not in prometheus_metrics:
            prometheus_metrics[metric_name] = 0
        
        prometheus_metrics[metric_name] += 1
        
        # Handle labeled metrics
        if labels:
            label_key = f"{metric_name}_labels"
            
            if label_key not in prometheus_metrics:
                prometheus_metrics[label_key] = {}
                
            label_str = "_".join(f"{k}_{v}" for k, v in sorted(labels.items()))
            
            if label_str not in prometheus_metrics[label_key]:
                prometheus_metrics[label_key][label_str] = 0
                
            prometheus_metrics[label_key][label_str] += 1


def set_gauge(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """
    Set a gauge metric to a specific value.
    
    Args:
        metric_name: Name of the gauge
        value: Value to set
        labels: Optional labels for the gauge
    """
    with metrics_lock:
        prometheus_metrics[metric_name] = value
        
        # Handle labeled metrics
        if labels:
            label_key = f"{metric_name}_labels"
            
            if label_key not in prometheus_metrics:
                prometheus_metrics[label_key] = {}
                
            label_str = "_".join(f"{k}_{v}" for k, v in sorted(labels.items()))
            prometheus_metrics[label_key][label_str] = value


def observe_histogram(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """
    Add an observation to a histogram metric.
    This is a simplified version for our metrics dict; a real Prometheus client
    would handle bucketing automatically.
    
    Args:
        metric_name: Name of the histogram
        value: Value to observe
        labels: Optional labels for the histogram
    """
    with metrics_lock:
        if f"{metric_name}_sum" not in prometheus_metrics:
            prometheus_metrics[f"{metric_name}_sum"] = 0
            prometheus_metrics[f"{metric_name}_count"] = 0
            
        prometheus_metrics[f"{metric_name}_sum"] += value
        prometheus_metrics[f"{metric_name}_count"] += 1
        
        # Handle labeled metrics
        if labels:
            label_key = f"{metric_name}_labels"
            
            if label_key not in prometheus_metrics:
                prometheus_metrics[label_key] = {}
                
            label_str = "_".join(f"{k}_{v}" for k, v in sorted(labels.items()))
            
            if f"{label_str}_sum" not in prometheus_metrics[label_key]:
                prometheus_metrics[label_key][f"{label_str}_sum"] = 0
                prometheus_metrics[label_key][f"{label_str}_count"] = 0
                
            prometheus_metrics[label_key][f"{label_str}_sum"] += value
            prometheus_metrics[label_key][f"{label_str}_count"] += 1 