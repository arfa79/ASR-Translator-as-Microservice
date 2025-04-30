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

4. Download VOSK model:
   - Download [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models)
   - Extract it to the project root directory

5. Set up RabbitMQ:
   - Install [Erlang](https://www.erlang.org/downloads)
   - Install [RabbitMQ Server](https://www.rabbitmq.com/download.html)
   - Start RabbitMQ service

6. Initialize Django:
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

### Testing

A test script is provided to verify system functionality:

```bash
cd tests
sh run_tests.sh
```

## Features

- Asynchronous processing using event-driven architecture
- Automatic file cleanup after processing
- Health monitoring for both services
- Rate limiting for API endpoints
- Comprehensive error handling and logging
- Support for WAV audio files
- Automatic retry logic for service connections

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
