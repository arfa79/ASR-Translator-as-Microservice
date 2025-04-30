#!/usr/bin/env python3
"""
Integration test for the ASR Translator microservice system.
This script tests the complete flow from uploading an audio file to receiving
the Persian translation.
"""

import os
import sys
import time
import json
import argparse
import requests
from termcolor import colored
from pathlib import Path

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

def print_json(data):
    """Print formatted JSON data"""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            print(data)
            return
    
    print(json.dumps(data, indent=2, ensure_ascii=False))

def test_upload(audio_file, base_url="http://localhost:8000"):
    """Test uploading an audio file to the service"""
    print_header("Testing Audio File Upload")
    
    if not os.path.exists(audio_file):
        print_error(f"Audio file not found: {audio_file}")
        return None
    
    try:
        print(f"Uploading file: {audio_file}")
        url = f"{base_url}/upload/"
        
        with open(audio_file, 'rb') as f:
            files = {'audio': f}
            response = requests.post(url, files=files)
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 202:
            print_success("Upload successful!")
            data = response.json()
            print("Response:")
            print_json(data)
            return data
        else:
            print_error(f"Upload failed with status code: {response.status_code}")
            print("Response:")
            print_json(response.text)
            return None
    
    except Exception as e:
        print_error(f"Error during upload: {str(e)}")
        return None

def test_translation_status(base_url="http://localhost:8000", max_attempts=30, delay=2):
    """Test checking the translation status until completion"""
    print_header("Testing Translation Status")
    
    try:
        url = f"{base_url}/translation/"
        attempts = 0
        
        while attempts < max_attempts:
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                print("Status:")
                print_json(data)
                
                # Check if translation is completed
                if 'translation' in data:
                    print_success("Processing completed successfully!")
                    print("Translation:", colored(data['translation'], "green"))
                    return data
                
                # Check if still processing
                if 'status' in data:
                    status = data['status']
                    print_warning(f"Still processing... Status: {status}")
                    attempts += 1
                    time.sleep(delay)
                    continue
            else:
                print_error(f"Failed to get status, code: {response.status_code}")
                print("Response:")
                print_json(response.text)
                return None
        
        print_error(f"Timeout after {max_attempts} attempts")
        return None
    
    except Exception as e:
        print_error(f"Error checking translation status: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Test ASR Translator System")
    parser.add_argument("audio_file", help="Path to audio file for testing")
    parser.add_argument("-u", "--url", default="http://localhost:8000",
                       help="Base URL of the service (default: http://localhost:8000)")
    parser.add_argument("-w", "--wait", type=int, default=30,
                       help="Maximum number of attempts to check status (default: 30)")
    parser.add_argument("-d", "--delay", type=int, default=2,
                       help="Delay between status checks in seconds (default: 2)")
    args = parser.parse_args()
    
    # Test file upload
    result = test_upload(args.audio_file, args.url)
    if not result:
        sys.exit(1)
    
    # Test translation status until completion
    result = test_translation_status(args.url, args.wait, args.delay)
    if not result:
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print_success("All tests completed successfully!")

if __name__ == "__main__":
    main()