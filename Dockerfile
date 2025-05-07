FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libsndfile1 \
    ffmpeg \
    unzip\
    netcat-traditional \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
     pip install -r requirements.txt

# Copy project
COPY . .

# Create directories
RUN mkdir -p /app/media/uploads /app/logs /app/staticfiles

# Set permissions
RUN chmod -R 755 /app

# Expose port
EXPOSE 8000

# Run entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "asr_translator.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"] 