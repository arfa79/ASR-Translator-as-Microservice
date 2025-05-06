"""
Tests for the ASR and translator worker components.
These tests verify that the worker components can process messages correctly.
"""
import os
import sys
import pytest
import json
import tempfile
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try importing the worker modules
try:
    from asr_system import ASRProcessor
    from translator_agent import TranslatorAgent
    ASR_AVAILABLE = True
except ImportError as e:
    print(f"ASR modules not importable: {e}")
    ASR_AVAILABLE = False


@pytest.mark.skipif(not ASR_AVAILABLE, reason="ASR modules not available")
class TestASRProcessor:
    """Tests for the ASR processor component."""
    
    @pytest.fixture
    def asr_processor(self):
        """Create an ASR processor for testing."""
        try:
            processor = ASRProcessor(
                model_path=os.environ.get('VOSK_MODEL_PATH', 'vosk-model-small-en-us-0.15'),
                use_parallel=False,  # Disable parallel processing for tests
                cache_dir=tempfile.mkdtemp(),
                use_cache=True
            )
            return processor
        except Exception as e:
            pytest.skip(f"Could not initialize ASR processor: {e}")
    
    def test_processor_initialization(self, asr_processor):
        """Test that the ASR processor initializes correctly."""
        assert asr_processor is not None, "ASR processor should initialize"
        assert hasattr(asr_processor, 'model'), "ASR processor should have a model attribute"
    
    def test_process_audio(self, asr_processor, sample_audio_file):
        """Test processing an audio file with the ASR processor."""
        if not sample_audio_file.exists():
            pytest.skip(f"Sample audio file not found: {sample_audio_file}")
        
        try:
            # Process the audio file
            result = asr_processor.process_file(str(sample_audio_file))
            
            # Check that we got a result
            assert result is not None, "ASR processing should return a result"
            assert isinstance(result, str), "ASR result should be a string"
        except Exception as e:
            pytest.fail(f"Error processing audio: {e}")


@pytest.mark.skipif(not ASR_AVAILABLE, reason="ASR modules not available")
class TestTranslatorAgent:
    """Tests for the translator agent component."""
    
    @pytest.fixture
    def translator_agent(self):
        """Create a translator agent for testing."""
        try:
            agent = TranslatorAgent(
                cache_dir=tempfile.mkdtemp(),
                use_cache=True
            )
            return agent
        except Exception as e:
            pytest.skip(f"Could not initialize translator agent: {e}")
    
    def test_agent_initialization(self, translator_agent):
        """Test that the translator agent initializes correctly."""
        assert translator_agent is not None, "Translator agent should initialize"
    
    def test_translate_text(self, translator_agent):
        """Test translating a text with the translator agent."""
        # Simple English text to translate
        text = "Hello world"
        
        try:
            # Translate the text
            result = translator_agent.translate(text, source_lang='en', target_lang='fa')
            
            # Check that we got a result
            assert result is not None, "Translation should return a result"
            assert isinstance(result, str), "Translation result should be a string"
            assert len(result) > 0, "Translation result should not be empty"
        except Exception as e:
            pytest.fail(f"Error translating text: {e}")


@pytest.mark.docker
def test_worker_environment_variables():
    """Test that the required environment variables for workers are available in Docker."""
    # This test is specifically for Docker environments
    if not os.environ.get('DOCKER_ENV'):
        pytest.skip("Not running in Docker environment")
    
    # Check for required environment variables
    required_vars = [
        'RABBITMQ_HOST', 'RABBITMQ_PORT', 'RABBITMQ_USER', 'RABBITMQ_PASSWORD',
        'REDIS_HOST', 'REDIS_PORT', 'VOSK_MODEL_PATH'
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    assert not missing_vars, f"Missing required environment variables: {', '.join(missing_vars)}" 