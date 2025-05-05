#!/bin/bash

set -e

# Wait for RabbitMQ to be ready
if [ "$RABBITMQ_HOST" ]; then
  echo "Waiting for RabbitMQ..."
  while ! nc -z $RABBITMQ_HOST $RABBITMQ_PORT; do
    sleep 0.1
  done
  echo "RabbitMQ is up and running"
fi

# Wait for Redis to be ready if not dummy
if [ "$REDIS_HOST" ] && [ "$REDIS_HOST" != "dummy" ]; then
  echo "Waiting for Redis..."
  while ! nc -z $REDIS_HOST $REDIS_PORT; do
    sleep 0.1
  done
  echo "Redis is up and running"
fi

# Install netcat for the health checks
apt-get update && apt-get install -y netcat-openbsd && apt-get clean

# Detect available CPU cores
CPU_CORES=$(nproc)
echo "Detected $CPU_CORES CPU cores available to container"

# Check container resource limits
CONTAINER_LIMITS=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo "not found")
CONTAINER_PERIOD=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null || echo "100000")

if [ "$CONTAINER_LIMITS" != "not found" ] && [ "$CONTAINER_LIMITS" != "-1" ]; then
  CONTAINER_CPUS=$(echo "scale=1; $CONTAINER_LIMITS / $CONTAINER_PERIOD" | bc)
  echo "Container CPU limit detected: $CONTAINER_CPUS CPUs"
  
  # Set environment variable for the app to know about container CPU limits
  export CONTAINER_CPU_LIMIT=$CONTAINER_CPUS
else
  echo "No container CPU limit detected, application will use internal CPU affinity settings"
  export CONTAINER_CPU_LIMIT=0
fi

# Check if models are downloaded
if [ "$SERVICE_TYPE" = "asr" ]; then
  echo "Checking ASR models..."
  if [ ! -d "/app/models/vosk/en-us" ]; then
    echo "VOSK model not found. Please check your model directory."
    exit 1
  fi
elif [ "$SERVICE_TYPE" = "translator" ]; then
  echo "Checking translator models..."
  # Add validation for argos model if needed
fi

# Check if we should override CPU affinity based on container environment
if [ -n "$CPU_AFFINITY" ]; then
  echo "CPU affinity override detected: $CPU_AFFINITY"
  export OVERRIDE_CPU_AFFINITY=$CPU_AFFINITY
fi

# Start appropriate service
if [ "$SERVICE_TYPE" = "asr" ]; then
  echo "Starting ASR service..."
  exec python asr_system.py
elif [ "$SERVICE_TYPE" = "translator" ]; then
  echo "Starting Translator service..."
  exec python translator_agent.py
else
  echo "Unknown service type: $SERVICE_TYPE"
  echo "Please set SERVICE_TYPE to 'asr' or 'translator'"
  exit 1
fi 