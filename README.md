# ASR-Translator-as-Microservice

A microservice-based system that performs Automatic Speech Recognition (ASR) on English audio files and translates the text to Persian. The system is built with Django and uses an Event-Driven Architecture (EDA) with RabbitMQ for communication between services.

## Table of Contents
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Traditional Setup](#traditional-setup)
  - [Docker Setup](#docker-setup)
- [Running the System](#running-the-system)
  - [Without Docker](#without-docker)
  - [With Docker](#with-docker)
- [Testing](#testing)
- [Usage](#usage)
- [Features](#features)
- [Docker Deployment](#docker-deployment)
- [Performance Tuning](#performance-tuning)
- [Dependencies](#dependencies)

## System Architecture

The system consists of three main components:

1. **API Gateway (Django)**: Handles file uploads and translation status requests
2. **ASR Service**: Performs speech-to-text conversion using VOSK
3. **Translation Service**: Translates English text to Persian using Argostranslate

All components communicate asynchronously through RabbitMQ events.

## Prerequisites

- Python 3.11+
- RabbitMQ Server
- VOSK English model (vosk-model-small-en-us-0.15)
- Docker (optional, for containerized deployment)
- Prometheus & Grafana (for monitoring)
- PostgreSQL (recommended) or SQLite
- Redis (for caching)

## Installation

### Traditional Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ASR-Translator-as-Microservice.git
cd ASR-Translator-as-Microservice
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Generate a .env file with secure settings
python generate_env.py

# Or create .env manually with necessary settings:
# SECRET_KEY, DB_* settings, etc.
```

5. Set up PostgreSQL:
```bash
# Install PostgreSQL if not already installed
# On Ubuntu/Debian:
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb asr_translator

# Or use the database settings you specified in the .env file
```

6. Download VOSK model:
   - Download [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip)
   - Extract it to the project root directory

7. Set up RabbitMQ:
   - Install [Erlang](https://www.erlang.org/downloads)
   - Install [RabbitMQ Server](https://www.rabbitmq.com/download.html)
   - Start RabbitMQ service

8. Set up Redis (optional, but recommended for caching):
```bash
# Install Redis if not already installed
# On Ubuntu/Debian:
sudo apt install redis-server

# Start Redis
sudo service redis-server start
```

9. Initialize Django:
```bash
python manage.py migrate
python manage.py createsuperuser  # Optional, for admin access
```

### Docker Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ASR-Translator-as-Microservice.git
cd ASR-Translator-as-Microservice
```

2. Create a `.env` file from the example template:
```bash
cp env.example .env
```

3. Edit the `.env` file to configure your environment:
   - Update `SECRET_KEY` with a secure key
   - Set database credentials
   - Configure other settings as needed

## Running the System

### Without Docker

You need to run three components in separate terminals:

1. Django Server:
```bash
python manage.py runserver
```

2. ASR Service:
```bash
python asr_system.py
```

3. Translation Service:
```bash
python translator_agent.py
```

4. (Optional) Run with metrics collection and autoscaling:
```bash
# Verify dependencies and configure autoscaling
./setup_autoscaling.sh

# Run the integrated system
python -m asr_translator.main
```

### With Docker

1. Build and start all services:
```bash
docker-compose up -d
```

2. Check service status:
```bash
docker-compose ps
```

3. Access the application:
   - Web API: http://localhost:8000/
   - RabbitMQ Management: http://localhost:15672/ (username/password from .env)
   - Prometheus: http://localhost:9090/
   - Grafana: http://localhost:3000/ (default admin/admin)

## Testing

The system includes a comprehensive testing suite in the `tests/` directory:

1. To test the VOSK speech recognition model:
```bash
python tests/test_vosk.py --audio path/to/audio.wav
```

2. To test the complete system end-to-end:
```bash
python tests/test_system.py path/to/audio.wav
```

3. To run all tests automatically:
```bash
./tests/run_tests.sh
```

## Usage

### API Endpoints

1. Upload Audio File:
```bash
POST http://localhost:8000/upload/
Content-Type: multipart/form-data
Body: audio=@your-file.wav
```

Response:
```json
{
    "status": "accepted",
    "file_id": "unique-identifier",
    "message": "File uploaded successfully and processing has begun"
}
```

2. Check Translation Status:
```bash
GET http://localhost:8000/translation/
```

Response:
```json
{
    "file_id": "unique-identifier",
    "translation": "Persian translation"  # If completed
}
```
or
```json
{
    "file_id": "unique-identifier",
    "status": "transcribing|translating"  # If in progress
}
```

## Features

### Core Features
- Asynchronous processing using event-driven architecture
- Automatic file cleanup after processing
- Health monitoring for both services
- Rate limiting for API endpoints
- Comprehensive error handling and logging
- Support for WAV audio files
- Automatic retry logic for service connections

### Performance Optimizations
- **Streaming Processing**: ASR processing in chunks for immediate feedback
- **Parallel Processing**: Large audio files split into segments and processed concurrently
- **Model Caching**: VOSK models loaded once and kept in memory
- **Translation Caching**: Redis-based caching for translations to avoid redundant work
- **Message Priorities**: RabbitMQ message priorities based on file size
- **CPU Affinity Settings**: Services assigned to specific CPU cores
- **Message Compression**: zlib compression for RabbitMQ messages
- **HTTP Streaming Responses**: Real-time updates to clients
- **PostgreSQL Database**: High-performance database for production use

### Performance Monitoring
The system includes a built-in metrics collection system using Prometheus:

1. **Setup Monitoring Stack**:
```bash
./monitoring/setup_monitoring.sh
cd monitoring
docker-compose up -d
```

2. **Available Metrics**:
   - Request Rates: Audio uploads, ASR requests, and translations
   - Processing Times: Duration measurements for each step
   - Resource Usage: Memory and CPU monitoring
   - Queue Sizes: RabbitMQ queue monitoring
   - Cache Hit Ratio: Translation cache performance

3. **Access Dashboards**:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (login with admin/admin)

### Autoscaling
The system can dynamically scale based on workload metrics:

1. **Setup Autoscaling**:
```bash
# Verify dependencies and configure autoscaling
./setup_autoscaling.sh

# Enable autoscaling
export ENABLE_AUTOSCALING=True
```

2. **Scaling Logic**:
   - Scales up when queue sizes exceed thresholds
   - Scales up when CPU usage is too high
   - Scales up when processing times are too long
   - Scales down during low load periods

3. **Configuration**: Customize thresholds via environment variables
```bash
export QUEUE_HIGH_THRESHOLD=10
export CPU_HIGH_THRESHOLD=70.0
export PROCESSING_TIME_THRESHOLD=30.0
```

## Docker Deployment

### Service Architecture

The Docker setup includes the following services:

1. **web**: Django API server for handling HTTP requests
2. **asr_worker**: Speech recognition worker service using VOSK
3. **translator_worker**: Text translation worker service using Argostranslate
4. **db**: PostgreSQL database for persistent data storage
5. **redis**: Redis cache for improved performance
6. **rabbitmq**: Message broker for communication between services
7. **prometheus**: Metrics collection for monitoring
8. **grafana**: Visualization dashboard for metrics

### Resource Management and CPU Affinity

#### Container Resource Settings

The Docker Compose configuration is designed to work with the application's internal CPU affinity and resource management:

- **CPU Limits**: Set to zero (`cpus: '0'`) to allow the application to manage its own CPU allocation through CPU affinity settings.
- **CPU Reservations**: Set minimum CPU resources that containers should have access to.
- **Memory Limits**: Set higher than required to accommodate peak usage and prevent OOM kills.

This approach allows the ASR and Translator services to:
1. Run their internal CPU affinity optimizations without container interference
2. Dynamically scale CPU usage based on workload
3. Properly handle parallel processing of audio files

#### Adjusting Resource Settings

If you observe resource-related issues:

1. Check application logs for affinity or resource errors
2. Adjust the container settings in `docker-compose.yml` as follows:
   - Increase memory limits if you see OOM errors
   - Adjust CPU reservations based on host capacity
   - Consider setting `cpus` limit if the application consumes too many resources

#### CPU Pinning for Production

For production deployments on multi-CPU systems, you may want to pin specific containers to specific CPUs to match the application's internal CPU affinity settings:

```bash
# Example: Run containers with specific CPU pinning (Docker run example)
docker run --cpuset-cpus="0,1" --name asr_worker_1 your-asr-image
```

This ensures the application's internal CPU affinity matches the container's CPU allocation.

### Scaling Docker Services

To scale the worker services:

```bash
# Scale ASR workers to 3 instances
docker-compose up -d --scale asr_worker=3

# Scale translator workers to 2 instances
docker-compose up -d --scale translator_worker=2
```

### Accessing Docker Logs

```bash
# View logs from all services
docker-compose logs

# View logs from a specific service
docker-compose logs web

# Follow logs in real-time
docker-compose logs -f asr_worker
```

### Common Docker Tasks

#### Database Migrations

```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

#### Creating a Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

#### Backing Up the Database

```bash
docker-compose exec db pg_dump -U postgres asr_translator > backup.sql
```

#### Restoring the Database

```bash
cat backup.sql | docker-compose exec -T db psql -U postgres asr_translator
```

### Stopping Docker Services

```bash
# Stop services but keep volumes and networks
docker-compose down

# Stop services and remove volumes (WARNING: This will delete all data)
docker-compose down -v
```

### Docker Troubleshooting

#### Container Won't Start

Check logs for the failing container:

```bash
docker-compose logs [service-name]
```

#### Database Connection Issues

Ensure PostgreSQL is running and the connection details in `.env` are correct:

```bash
docker-compose exec db psql -U postgres -c "SELECT 1"
```

#### Models Not Loading

Check if models are correctly mounted in the volumes:

```bash
docker-compose exec asr_worker ls -la /app/models/vosk
```

#### Resource-Related Issues

If you're experiencing issues related to CPU or memory:

```bash
# Check container resource usage
docker stats

# View container details including resource limits
docker inspect asr_worker_1 | grep -A 20 "HostConfig"
```

### Docker Production Deployment Notes

For production deployments:

1. Use proper SSL/TLS termination with a reverse proxy like Nginx
2. Set `DEBUG=False` in the .env file
3. Use strong, unique passwords for all services
4. Consider using Docker Swarm or Kubernetes for advanced orchestration
5. Set up regular backups of the database and media files
6. Use proper monitoring and alerting

### Docker Security Considerations

- The Docker Compose setup exposes several ports to the host. In production, consider restricting access using a proper network configuration.
- Default credentials are included in the env.example file. Always change these for production deployments.
- Secret management: Consider using Docker secrets or a dedicated solution like HashiCorp Vault for managing sensitive information.

## Performance Tuning

### Database Optimization
- Proper indexes have been added to commonly queried fields
- Custom QuerySets and Managers optimize database access patterns
- Bulk operations are used for efficiency with large datasets

### Container Performance
The `deploy` section in the compose file includes resource reservations and limits for the worker containers. The default configuration is designed to work with the application's internal CPU affinity and resource management features, but you may need to adjust based on your server capacity and workload requirements.

## Dependencies

The project uses dependencies with specific versions as defined in `requirements.txt`:

- **Web Framework**: Django==5.2, djangorestframework==3.14.0
- **Speech Recognition**: vosk==0.3.45, SoundFile==0.10.3.post1
- **Translation**: argostranslate==1.8.0
- **Messaging**: pika==1.3.2
- **Caching**: redis==4.5.5, django-redis==5.2.0
- **Database**: psycopg2-binary==2.9.6
- **Monitoring**: prometheus-client==0.16.0
- **HTTP**: requests==2.28.2
- **Utils**: python-dotenv==1.0.0, numpy==1.24.3
