# Performance Monitoring for ASR-Translator Microservice

This document explains how to use the performance monitoring system we've added to the ASR-Translator-as-Microservice. The monitoring system helps you track key metrics to understand system performance, identify bottlenecks, and make data-driven optimization decisions.

## Features

The monitoring system tracks:

- **Request Rates**: Number of audio uploads, ASR requests, and translation requests over time
- **Processing Times**: How long each step in the pipeline takes (ASR, translation, and end-to-end)
- **Resource Usage**: Memory and CPU usage by service
- **Queue Sizes**: Number of messages waiting in RabbitMQ queues
- **Cache Performance**: Translation cache hit ratio
- **Error Rates**: Count of different types of errors by service

## Architecture

The monitoring system consists of:

1. **Metrics Collection**: Using Prometheus Python client in the application code
2. **Metrics Storage**: Prometheus time-series database
3. **Visualization**: Grafana dashboards

## Setup Instructions

### Step 1: Install Dependencies

```bash
pip install prometheus_client
```

This was already added to the requirements.txt file.

### Step 2: Start the Monitoring Stack

We've created a setup script that installs and configures Prometheus and Grafana:

```bash
./monitoring/setup_monitoring.sh
cd monitoring
docker-compose up -d
```

### Step 3: Access the Dashboards

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (login with admin/admin)

## Available Metrics

### Counters
- `audio_uploads_total`: Total number of audio file uploads
- `asr_requests_total`: Total number of ASR requests
- `translation_requests_total`: Total number of translation requests
- `errors_total`: Total number of errors by service and type

### Timings
- `audio_upload_duration_seconds`: Time taken to upload audio files
- `asr_processing_duration_seconds`: Time taken for ASR processing
- `translation_duration_seconds`: Time taken for translation
- `end_to_end_duration_seconds`: Time taken for complete processing pipeline

### Resource Usage
- `memory_usage_bytes`: Memory usage by service
- `cpu_usage_percent`: CPU usage percentage by service

### Other Metrics
- `rabbitmq_queue_size`: Number of messages in each RabbitMQ queue
- `audio_processing_tasks`: Number of tasks by status
- `cache_hit_ratio`: Cache hit ratio for translation cache

## Configuration

The monitoring system runs on these ports by default:
- ASR service metrics: 8001
- Translator service metrics: 8002
- Django web app metrics: 8000
- Prometheus: 9090
- Grafana: 3000

You can change these ports in the monitoring/prometheus/prometheus.yml file.

## Troubleshooting

If you don't see metrics in Grafana:
1. Check that all services are running
2. Verify Prometheus can reach each service endpoint
3. Check that each service is exposing metrics correctly

## Adding Custom Metrics

To add your own metrics to any service, use the functions provided in `asr_translator/metrics.py`:

```python
from asr_translator.metrics import record_error, Timer, my_custom_metric

# Record an error
record_error('my_service', 'my_error_type')

# Time an operation
with Timer(my_operation_duration):
    # Your code here
    pass
``` 