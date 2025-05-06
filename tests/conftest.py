import os
import sys
import pytest
import wave
from pathlib import Path
import requests
import time
import tempfile
import pytest
from vosk import Model, KaldiRecognizer

# Add project root to sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(scope="session")
def test_dir():
    """Return the path to the tests directory."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def data_dir(test_dir):
    """Return the path to the test data directory, creating it if it doesn't exist."""
    data_path = test_dir / "data"
    data_path.mkdir(exist_ok=True)
    return data_path


@pytest.fixture(scope="session")
def sample_audio_file(data_dir):
    """Create a sample audio file for testing if it doesn't exist."""
    sample_audio_path = data_dir / "sample_test.wav"
    
    # If the file already exists, return its path
    if sample_audio_path.exists():
        return sample_audio_path
    
    # Try to find an existing WAV file in the media directory
    media_dir = Path("media/uploads")
    if media_dir.exists():
        for file in media_dir.glob("*.wav"):
            if file.exists():
                return file
    
    # If no file found, create a simple WAV file
    try:
        import numpy as np
        from scipy.io import wavfile
        
        # Create a simple sine wave
        sample_rate = 16000
        duration = 2  # seconds
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        data = np.sin(2 * np.pi * 440 * t) * 32767  # 440 Hz sine wave
        data = data.astype(np.int16)
        
        # Save as WAV file
        wavfile.write(sample_audio_path, sample_rate, data)
        
        return sample_audio_path
    except ImportError:
        pytest.skip("scipy not available to create sample audio file")


@pytest.fixture(scope="session")
def vosk_model():
    """Load the VOSK model for testing."""
    model_path = os.environ.get("VOSK_MODEL_PATH", "vosk-model-small-en-us-0.15")
    
    if not os.path.exists(model_path):
        pytest.skip(f"VOSK model not found at {model_path}")
    
    try:
        return Model(model_path)
    except Exception as e:
        pytest.skip(f"Failed to load VOSK model: {str(e)}")


@pytest.fixture(scope="session")
def service_url():
    """Return the URL of the ASR-Translator service."""
    return os.environ.get("SERVICE_URL", "http://localhost:8000")


@pytest.fixture
def check_service_availability(service_url):
    """Check if the service is available before running tests."""
    try:
        response = requests.get(f"{service_url}/health/", timeout=5)
        if response.status_code != 200:
            pytest.skip(f"Service not available at {service_url}, status code: {response.status_code}")
    except requests.RequestException:
        pytest.skip(f"Service not available at {service_url}") 