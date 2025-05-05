#!/bin/bash

# Setup script for autoscaling dependencies and configuration

echo "Setting up ASR-Translator Autoscaling..."

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "Error: pip not found. Please install pip first."
    exit 1
fi

# Verify required dependencies are installed
echo "Verifying dependencies..."
if python -c "import prometheus_client, requests, pydub" 2>/dev/null; then
    echo "✓ Required dependencies are already installed!"
else
    echo "Some dependencies might be missing. Make sure all requirements are installed:"
    echo "pip install -r requirements.txt"
    echo "× Please install all dependencies and try again."
    exit 1
fi

# Create example configuration file
CONFIG_FILE=".autoscaler.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating example configuration file: $CONFIG_FILE"
    cat > "$CONFIG_FILE" << EOF
# ASR-Translator Autoscaler Configuration
ENABLE_AUTOSCALING=True
PROMETHEUS_URL=http://localhost:9090
AUTOSCALE_CHECK_INTERVAL=30
MAX_ASR_INSTANCES=3
MAX_TRANSLATOR_INSTANCES=3
MIN_INSTANCES=1
QUEUE_HIGH_THRESHOLD=10
QUEUE_LOW_THRESHOLD=2
CPU_HIGH_THRESHOLD=70.0
CPU_LOW_THRESHOLD=20.0
PROCESSING_TIME_THRESHOLD=30.0
EOF
    echo "✓ Created example configuration file: $CONFIG_FILE"
else
    echo "Configuration file already exists: $CONFIG_FILE"
fi

# Show instructions for next steps
echo ""
echo "Setup completed successfully!"
echo ""
echo "To use autoscaling:"
echo "1. Make sure Prometheus is running and collecting metrics"
echo "2. Source the configuration file: source $CONFIG_FILE"
echo "3. Start the system: python -m asr_translator.main"
echo ""
echo "For more details, see the README.md"

# Make script executable
chmod +x setup_autoscaling.sh 