from vosk import Model, KaldiRecognizer
import os
import json
import wave
import sys

try:
    print("Attempting to load model...")
    model_path = "vosk-model-small-en-us-0.15"
    if not os.path.exists(model_path):
        print(f"Model path '{model_path}' does not exist")
        sys.exit(1)
        
    # List directories in model path
    print(f"Model directory contents: {os.listdir(model_path)}")
    
    # Create model
    model = Model(model_path)
    print("Model loaded successfully!")
    
    # Try to create a recognizer (this checks if the model is initialized correctly)
    recognizer = KaldiRecognizer(model, 16000)
    print("Recognizer created successfully!")
    
    print("VOSK test passed!")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 