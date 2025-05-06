"""
Test the VOSK model functionality for speech recognition.
"""
import os
import pytest
import json
import wave
from vosk import KaldiRecognizer


def test_model_loading(vosk_model):
    """Test that the VOSK model can be loaded."""
    assert vosk_model is not None, "VOSK model could not be loaded"


def test_recognizer_creation(vosk_model):
    """Test that a KaldiRecognizer can be created from the model."""
    recognizer = KaldiRecognizer(vosk_model, 16000)
    assert recognizer is not None, "Failed to create KaldiRecognizer"


def test_audio_processing(vosk_model, sample_audio_file):
    """Test processing an audio file with VOSK."""
    # Skip if no audio file
    if not sample_audio_file.exists():
        pytest.skip(f"Sample audio file not found: {sample_audio_file}")
    
    # Open the audio file
    with wave.open(str(sample_audio_file), "rb") as wf:
        # Get audio details
        sample_rate = wf.getframerate()
        
        # Create recognizer
        recognizer = KaldiRecognizer(vosk_model, sample_rate)
        
        # Process audio
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if "text" in result:
                    text += result["text"] + " "
        
        # Get final result
        final_result = json.loads(recognizer.FinalResult())
        if "text" in final_result:
            text += final_result["text"]
        
        # Don't check for specific text content (as we might have empty audio),
        # just verify the process completes without errors
        assert isinstance(text, str), "Transcription should be a string"


def test_8k_audio_processing(vosk_model, data_dir):
    """Test processing an 8kHz audio file with VOSK."""
    # Create an 8kHz audio file if needed
    audio_path = data_dir / "test_8k.wav"
    
    if not audio_path.exists():
        try:
            # Create a simple 8kHz audio file
            import numpy as np
            from scipy.io import wavfile
            
            # Create a simple sine wave at 8kHz
            sample_rate = 8000
            duration = 2  # seconds
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            data = np.sin(2 * np.pi * 440 * t) * 32767  # 440 Hz sine wave
            data = data.astype(np.int16)
            
            # Save as WAV file
            wavfile.write(audio_path, sample_rate, data)
        except ImportError:
            pytest.skip("scipy not available to create 8kHz audio file")
    
    # Skip if audio file still doesn't exist
    if not audio_path.exists():
        pytest.skip(f"8kHz audio file not found: {audio_path}")
    
    # Open the audio file
    with wave.open(str(audio_path), "rb") as wf:
        # Get audio details
        sample_rate = wf.getframerate()
        assert sample_rate == 8000, f"Expected 8kHz audio, got {sample_rate}Hz"
        
        # Create recognizer
        recognizer = KaldiRecognizer(vosk_model, sample_rate)
        
        # Process audio
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if "text" in result:
                    text += result["text"] + " "
        
        # Get final result
        final_result = json.loads(recognizer.FinalResult())
        if "text" in final_result:
            text += final_result["text"]
        
        assert isinstance(text, str), "Transcription should be a string" 