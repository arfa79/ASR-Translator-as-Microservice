import requests
import time
import sys
import os

def test_upload_endpoint(file_path):
    """Test the upload endpoint with a WAV file"""
    print("\nTesting file upload...")
    
    if not os.path.exists(file_path):
        print(f"Error: Test file {file_path} not found!")
        return False
        
    url = "http://localhost:8000/upload/"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'audio': f}
            response = requests.post(url, files=files)
            
        if response.status_code == 202:
            print("Upload successful!")
            print(f"Response: {response.json()}")
            return response.json().get('file_id')
        else:
            print(f"Upload failed with status code: {response.status_code}")
            print(f"Error: {response.json()}")
            return None
            
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        return None

def test_translation_status(file_id=None):
    """Test the translation status endpoint"""
    print("\nChecking translation status...")
    
    url = "http://localhost:8000/translation/"
    max_attempts = 30  # Maximum number of attempts (5 minutes with 10-second intervals)
    
    try:
        for attempt in range(max_attempts):
            response = requests.get(url)
            
            if response.status_code == 200:
                status_data = response.json()
                print(f"Status: {status_data}")
                
                # If we're tracking a specific file_id
                if file_id and status_data.get('file_id') != file_id:
                    print("Warning: Status is for a different file")
                    return False
                
                # Check if processing is complete
                if 'translation' in status_data:
                    print("\nProcessing completed successfully!")
                    print(f"Translation: {status_data['translation']}")
                    return True
                elif status_data.get('status') in ['uploaded', 'transcribing', 'translating']:
                    print(f"Still processing... Status: {status_data['status']}")
                    time.sleep(10)  # Wait 10 seconds before next check
                    continue
                    
            else:
                print(f"Status check failed with status code: {response.status_code}")
                print(f"Error: {response.json()}")
                return False
                
        print("\nTimeout: Processing took too long!")
        return False
        
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        return False

def main():
    # Check if test file path is provided
    if len(sys.argv) != 2:
        print("Usage: python test_system.py path/to/test.wav")
        sys.exit(1)
        
    test_file = sys.argv[1]
    
    # Test upload
    file_id = test_upload_endpoint(test_file)
    if not file_id:
        print("Upload test failed!")
        sys.exit(1)
        
    # Test translation status
    if not test_translation_status(file_id):
        print("Translation test failed!")
        sys.exit(1)
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    main()