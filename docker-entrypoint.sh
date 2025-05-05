#!/bin/bash

set -e

# Wait for PostgreSQL to be ready
if [ "$DATABASE_HOST" ]; then
  echo "Waiting for PostgreSQL..."
  while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
    sleep 0.1
  done
  echo "PostgreSQL is up and running"
fi

# Wait for RabbitMQ to be ready
if [ "$RABBITMQ_HOST" ]; then
  echo "Waiting for RabbitMQ..."
  while ! nc -z $RABBITMQ_HOST $RABBITMQ_PORT; do
    sleep 0.1
  done
  echo "RabbitMQ is up and running"
fi

# Wait for Redis to be ready
if [ "$REDIS_HOST" ] && [ "$REDIS_HOST" != "dummy" ]; then
  echo "Waiting for Redis..."
  while ! nc -z $REDIS_HOST $REDIS_PORT; do
    sleep 0.1
  done
  echo "Redis is up and running"
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create cache table if needed
echo "Creating cache table..."
python manage.py createcachetable

# Start server
echo "Starting server..."
exec "$@" 