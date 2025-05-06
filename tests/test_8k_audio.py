from vosk import Model, KaldiRecognizer
import os
import json
import wave
import sys

try:
    print("Attempting to load model...")
    model_path = "../vosk-model-small-en-us-0.15/"
    if not os.path.exists(model_path):
        print(f"Model path '{model_path}' does not exist")
        sys.exit(1)
        
    # List audio files in media/uploads
    media_dir = "../media/uploads"
    if os.path.exists(media_dir):
        print(f"Audio files in {media_dir}:")
        for file in os.listdir(media_dir):
            if file.endswith(".wav"):
                print(f"  - {file}")
    
    # Find a sample wav file
    test_file = None
    for root, dirs, files in os.walk("../media/uploads"):
        for file in files:
            if file.endswith(".wav"):
                test_file = os.path.join(root, file)
                break
        if test_file:
            break
    
    if not test_file:
        print("No WAV file found for testing")
        sys.exit(1)
    
    print(f"Testing with audio file: {test_file}")
    
    # Open and analyze the wav file
    wf = wave.open(test_file, "rb")
    sample_rate = wf.getframerate()
    channels = wf.getnchannels()
    width = wf.getsampwidth()
    
    print(f"Audio file details:")
    print(f"  - Sample rate: {sample_rate} Hz")
    print(f"  - Channels: {channels}")
    print(f"  - Sample width: {width} bytes")
    
    # Create model and recognizer
    model = Model(model_path)
    recognizer = KaldiRecognizer(model, sample_rate)
    
    # Process audio
    print("Processing audio...")
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
            print(f"Error processing frame: {str(e)}")
            continue
    
    final_result = json.loads(recognizer.FinalResult())
    if "text" in final_result:
        text += final_result["text"]
    
    print(f"Transcription: {text.strip()}")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 