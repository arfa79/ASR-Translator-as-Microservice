#!/usr/bin/env python
"""
This script generates a .env file for the ASR-Translator microservice.
It creates secure settings and prompts for database credentials.
"""

import os
import secrets
import string
import getpass

def generate_secret_key(length=50):
    """Generate a secure random secret key."""
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    env_file = '.env'
    
    # Check if .env already exists
    if os.path.exists(env_file):
        overwrite = input(f"{env_file} already exists. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Aborted.")
            return
    
    # Generate a secure secret key
    secret_key = generate_secret_key()
    
    # Get database details
    print("\nDatabase Configuration")
    print("---------------------")
    use_postgres = input("Use PostgreSQL? (y/n, default: y): ").lower() != 'n'
    
    if use_postgres:
        db_name = input("Database name (default: asr_translator): ") or 'asr_translator'
        db_user = input("Database user (default: postgres): ") or 'postgres'
        db_password = getpass.getpass("Database password: ")
        db_host = input("Database host (default: localhost): ") or 'localhost'
        db_port = input("Database port (default: 5432): ") or '5432'
        db_engine = 'django.db.backends.postgresql'
    else:
        db_name = 'db.sqlite3'
        db_user = ''
        db_password = ''
        db_host = ''
        db_port = ''
        db_engine = 'django.db.backends.sqlite3'

    # Other settings
    debug = input("\nEnable Debug mode? (y/n, default: y): ").lower() != 'n'
    allowed_hosts = input("Allowed hosts (comma-separated, default: localhost,127.0.0.1): ") or 'localhost,127.0.0.1'
    
    # Advanced settings
    print("\nAdvanced Settings")
    print("----------------")
    show_advanced = input("Configure advanced settings? (y/n, default: n): ").lower() == 'y'
    
    if show_advanced:
        rabbitmq_host = input("RabbitMQ host (default: localhost): ") or 'localhost'
        rabbitmq_port = input("RabbitMQ port (default: 5672): ") or '5672'
        rabbitmq_exchange = input("RabbitMQ exchange (default: audio_events): ") or 'audio_events'
        
        redis_host = input("Redis host (default: localhost): ") or 'localhost'
        redis_port = input("Redis port (default: 6379): ") or '6379'
        redis_db = input("Redis DB (default: 0): ") or '0'
        
        enable_autoscaling = input("Enable autoscaling? (y/n, default: n): ").lower() == 'y'
    else:
        rabbitmq_host = 'localhost'
        rabbitmq_port = '5672'
        rabbitmq_exchange = 'audio_events'
        redis_host = 'localhost'
        redis_port = '6379'
        redis_db = '0'
        enable_autoscaling = False
    
    # Create the .env file
    with open(env_file, 'w') as f:
        f.write(f"# Django settings\n")
        f.write(f"SECRET_KEY={secret_key}\n")
        f.write(f"DEBUG={'True' if debug else 'False'}\n")
        f.write(f"ALLOWED_HOSTS={allowed_hosts}\n")
        
        f.write(f"\n# Database settings\n")
        f.write(f"DB_ENGINE={db_engine}\n")
        f.write(f"DB_NAME={db_name}\n")
        f.write(f"DB_USER={db_user}\n")
        f.write(f"DB_PASSWORD={db_password}\n")
        f.write(f"DB_HOST={db_host}\n")
        f.write(f"DB_PORT={db_port}\n")
        
        f.write(f"\n# RabbitMQ settings\n")
        f.write(f"RABBITMQ_HOST={rabbitmq_host}\n")
        f.write(f"RABBITMQ_PORT={rabbitmq_port}\n")
        f.write(f"RABBITMQ_EXCHANGE={rabbitmq_exchange}\n")
        
        f.write(f"\n# Redis settings (for caching)\n")
        f.write(f"REDIS_HOST={redis_host}\n")
        f.write(f"REDIS_PORT={redis_port}\n")
        f.write(f"REDIS_DB={redis_db}\n")
        
        f.write(f"\n# Autoscaling settings\n")
        f.write(f"ENABLE_AUTOSCALING={'True' if enable_autoscaling else 'False'}\n")
        f.write(f"PROMETHEUS_URL=http://localhost:9090\n")
        f.write(f"MAX_ASR_INSTANCES=3\n")
        f.write(f"MAX_TRANSLATOR_INSTANCES=3\n")
        f.write(f"MIN_INSTANCES=1\n")
        f.write(f"QUEUE_HIGH_THRESHOLD=10\n")
        f.write(f"QUEUE_LOW_THRESHOLD=2\n")
        f.write(f"CPU_HIGH_THRESHOLD=70.0\n")
        f.write(f"CPU_LOW_THRESHOLD=20.0\n")
        f.write(f"PROCESSING_TIME_THRESHOLD=30.0\n")
    
    print(f"\n.env file created successfully!")
    print(f"You may need to install PostgreSQL and run:")
    print(f"  createdb {db_name}")
    
    if use_postgres:
        print("\nMake sure to install the PostgreSQL dependencies:")
        print("  pip install psycopg2-binary")
    
    print("\nTo apply database migrations, run:")
    print("  python manage.py migrate")

if __name__ == "__main__":
    main() 