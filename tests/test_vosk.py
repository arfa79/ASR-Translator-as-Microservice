#!/usr/bin/env python3
"""
Test script for VOSK model initialization and audio processing.
This script verifies that the VOSK model can be loaded and used for speech recognition.
"""

import os
import sys
import json
import wave
import argparse
from termcolor import colored

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    print("Error: VOSK module not found. Please install it with 'pip install vosk'")
    sys.exit(1)

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(colored(f"  {title}", "cyan", attrs=["bold"]))
    print("=" * 80)

def print_success(message):
    """Print a success message"""
    print(colored("✓ " + message, "green"))

def print_warning(message):
    """Print a warning message"""
    print(colored("⚠ " + message, "yellow"))

def print_error(message):
    """Print an error message"""
    print(colored("✗ " + message, "red"))

def test_model_loading(model_path):
    """Test that the VOSK model can be loaded"""
    print_header("Testing VOSK Model Loading")
    
    if not os.path.exists(model_path):
        print_error(f"Model path '{model_path}' does not exist")
        return False
    
    try:
        # List directories in model path
        print(f"Model directory contents: {os.listdir(model_path)}")
        
        # Create model
        model = Model(model_path)
        print_success("Model loaded successfully!")
        
        # Try to create a recognizer (this checks if the model is initialized correctly)
        recognizer = KaldiRecognizer(model, 16000)
        print_success("Recognizer created successfully!")
        
        return model
    except Exception as e:
        print_error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_processing(model, audio_path):
    """Test processing an audio file with VOSK"""
    print_header("Testing Audio Processing")
    
    if not os.path.exists(audio_path):
        print_error(f"Audio file '{audio_path}' not found")
        return False
    
    try:
        # Open the audio file
        wf = wave.open(audio_path, "rb")
        
        # Get audio details
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        
        print(f"Audio file details:")
        print(f"  - File: {audio_path}")
        print(f"  - Sample rate: {sample_rate} Hz")
        print(f"  - Channels: {channels}")
        print(f"  - Sample width: {width} bytes")
        
        # Create recognizer
        recognizer = KaldiRecognizer(model, sample_rate)
        
        # Process audio
        print("\nProcessing audio...")
        text = ""
        
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            try:
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    if "text" in result:
                        text += result["text"] + " "
            except Exception as e:
                print_warning(f"Error processing frame: {str(e)}")
                continue
        
        final_result = json.loads(recognizer.FinalResult())
        if "text" in final_result:
            text += final_result["text"]
        
        # Display result
        if text.strip():
            print_success(f"Transcription: {text.strip()}")
        else:
            print_warning("No speech detected in the audio file")
        
        return True
    except Exception as e:
        print_error(f"Error processing audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Test VOSK speech recognition model")
    parser.add_argument("-m", "--model", default="vosk-model-small-en-us-0.15", 
                      help="Path to VOSK model directory")
    parser.add_argument("-a", "--audio", help="Path to audio file for testing")
    args = parser.parse_args()
    
    # Test model loading
    model = test_model_loading(args.model)
    if not model:
        print_error("Model loading test failed")
        sys.exit(1)
    
    print_success("VOSK test passed!")
    
    # Test audio processing if a file was provided
    if args.audio:
        success = test_audio_processing(model, args.audio)
        if not success:
            print_error("Audio processing test failed")
            sys.exit(1)
        print_success("Audio processing test passed!")

if __name__ == "__main__":
    main() 