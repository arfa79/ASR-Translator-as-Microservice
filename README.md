# ASR-Translator-as-Microservice

A microservice-based system that performs Automatic Speech Recognition (ASR) on English audio files and translates the text to Persian. The system is built with Django and uses an Event-Driven Architecture (EDA) with RabbitMQ for communication between services.

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
- Docker 
- Prometheus & Grafana
- PostgreSQL (recommended) or SQLite
- Redis (for caching)

## Installation

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

## Running the System

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

## Dependencies

The project uses dependencies with specific versions as defined in `requirements.txt`:

- **Web Framework**: Django==5.2, djangorestframework==3.14.0
- **Speech Recognition**: vosk==0.3.45, SoundFile==0.10.3.post1
- **Translation**: argostranslate==1.9.6
- **Messaging**: pika==1.3.2 (RabbitMQ client)
- **Caching**: redis==5.0.0, django-redis==5.3.0
- **Database**: psycopg2-binary==2.9.6 (PostgreSQL)
- **Monitoring**: prometheus_client==0.17.1, psutil==5.9.6
- **Audio Processing**: pydub==0.25.1
- **HTTP**: requests==2.32.3
- **Environment**: python-dotenv==1.0.0

All dependencies use pinned versions to ensure consistent behavior across environments.

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the project root:

```
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=asr_translator
DB_USER=postgres
DB_PASSWORD=your-password-here
DB_HOST=localhost
DB_PORT=5432

# Other settings...
```

You can generate a complete `.env` file with secure values by running:
```bash
python generate_env.py
```

## Limitations

- Only supports WAV audio files
- Maximum file size: 10MB
- Rate limit: 10 requests per minute per IP
- English to Persian translation only

## Error Handling

The system includes comprehensive error handling:
- Connection retry logic for RabbitMQ
- Automatic file cleanup on errors
- Health checks for all services
- Detailed logging across all components

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [VOSK](https://alphacephei.com/vosk/) for speech recognition
- [Argostranslate](https://www.argosopentech.com/) for translation
- [RabbitMQ](https://www.rabbitmq.com/) for message queuing
- [Django](https://www.djangoproject.com/) for the web framework
- [Prometheus](https://prometheus.io/) for metrics collection
- [Grafana](https://grafana.com/) for metrics visualization
- [PostgreSQL](https://www.postgresql.org/) for database
- [Redis](https://redis.io/) for caching
