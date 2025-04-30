#!/bin/bash

# Set colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print a header
print_header() {
    echo -e "\n${CYAN}========================================================================"
    echo -e "  $1"
    echo -e "========================================================================${NC}"
}

# Print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

# Find model directory
MODEL_DIR=""
for model in "vosk-model-small-en-us-0.15" "vosk-model-en-us-0.22"; do
    if [ -d "$model" ]; then
        MODEL_DIR="$model"
        print_success "Found VOSK model: $MODEL_DIR"
        break
    fi
done

if [ -z "$MODEL_DIR" ]; then
    print_error "VOSK model directory not found! Please download either vosk-model-small-en-us-0.15 or vosk-model-en-us-0.22."
    exit 1
fi

# Find test audio file
TEST_AUDIO=""
for file in media/uploads/*.wav; do
    if [ -f "$file" ]; then
        TEST_AUDIO="$file"
        print_success "Found test audio file: $TEST_AUDIO"
        break
    fi
done

if [ -z "$TEST_AUDIO" ]; then
    print_error "No test audio files found in media/uploads/ directory!"
    exit 1
fi

print_header "ASR Translator Microservice Test Suite"

# Check if required packages are installed
print_header "Checking Required Packages"
pip install -q termcolor requests

# Check if services are running
print_header "Checking Services"

# Check Django server
if ! curl -s "http://localhost:8000/translation/" > /dev/null; then
    print_warning "Django server might not be running. Starting it in the background..."
    python manage.py runserver > django_server.log 2>&1 &
    DJANGO_PID=$!
    sleep 2
    echo "Django server started with PID: $DJANGO_PID"
else
    print_success "Django server is running"
fi

# Test VOSK model loading
print_header "Running VOSK Model Test"
python tests/test_vosk.py --model "$MODEL_DIR" --audio "$TEST_AUDIO"
if [ $? -ne 0 ]; then
    print_error "VOSK model test failed!"
    exit 1
fi

# Test system with audio file
print_header "Running System Integration Test"
python tests/test_system.py "$TEST_AUDIO" --wait 20 --delay 2
if [ $? -ne 0 ]; then
    print_error "System integration test failed!"
    exit 1
fi

print_header "All Tests Completed Successfully!"

# Clean up
if [ ! -z ${DJANGO_PID+x} ]; then
    kill $DJANGO_PID
    print_success "Stopped Django server"
fi 