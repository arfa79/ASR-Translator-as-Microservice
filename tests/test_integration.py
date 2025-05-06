"""
Integration tests for the ASR Translator microservice system.
These tests verify the end-to-end flow from uploading an audio file
to receiving the Persian translation.
"""
import os
import pytest
import time
import requests
import json


@pytest.mark.integration
@pytest.mark.usefixtures("check_service_availability")
class TestASRTranslatorSystem:
    """Test the end-to-end functionality of the ASR Translator system."""
    
    def test_health_endpoint(self, service_url):
        """Test that the health endpoint returns 200 OK."""
        response = requests.get(f"{service_url}/health/")
        assert response.status_code == 200, "Health endpoint should return 200 OK"
    
    def test_file_upload(self, service_url, sample_audio_file):
        """Test uploading an audio file to the service."""
        url = f"{service_url}/upload/"
        
        with open(sample_audio_file, 'rb') as f:
            files = {'audio': f}
            response = requests.post(url, files=files)
        
        assert response.status_code == 202, f"Expected status code 202, got {response.status_code}"
        
        # Verify response format
        data = response.json()
        assert "message" in data, "Response should contain a 'message' field"
        assert "id" in data, "Response should contain an 'id' field"
        assert "status" in data, "Response should contain a 'status' field"
    
    def test_translation_flow(self, service_url, sample_audio_file):
        """Test the complete flow from uploading to getting translation."""
        # First upload the file
        url = f"{service_url}/upload/"
        with open(sample_audio_file, 'rb') as f:
            files = {'audio': f}
            response = requests.post(url, files=files)
        
        assert response.status_code == 202, "File upload failed"
        upload_data = response.json()
        
        # Check translation status until completion or timeout
        max_attempts = 30
        delay = 2  # seconds between attempts
        status_url = f"{service_url}/translation/"
        
        for attempt in range(max_attempts):
            response = requests.get(status_url)
            assert response.status_code == 200, f"Status check failed with code {response.status_code}"
            
            data = response.json()
            
            # Check if translation is completed
            if 'translation' in data:
                # Test passes if we get a translation (content doesn't matter for test)
                assert isinstance(data['translation'], str), "Translation should be a string"
                return
            
            # Check if still processing
            if 'status' in data:
                # Wait and try again
                time.sleep(delay)
                continue
        
        # If we get here, we've timed out
        pytest.fail(f"Translation did not complete within {max_attempts * delay} seconds")


@pytest.mark.parametrize("endpoint", [
    "/health/",
    "/metrics/"
])
def test_service_endpoints(service_url, endpoint, check_service_availability):
    """Test that various service endpoints are accessible."""
    response = requests.get(f"{service_url}{endpoint}")
    assert response.status_code == 200, f"Endpoint {endpoint} should return 200 OK"


@pytest.mark.skipif(not os.environ.get("RUN_STRESS_TESTS"), 
                    reason="Stress tests only run when RUN_STRESS_TESTS is set")
@pytest.mark.usefixtures("check_service_availability")
def test_concurrent_uploads(service_url, sample_audio_file):
    """Test uploading multiple files concurrently."""
    import concurrent.futures
    
    def upload_file():
        with open(sample_audio_file, 'rb') as f:
            files = {'audio': f}
            response = requests.post(f"{service_url}/upload/", files=files)
        return response.status_code
    
    # Upload 5 files concurrently
    num_uploads = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_uploads) as executor:
        results = list(executor.map(lambda _: upload_file(), range(num_uploads)))
    
    # Check that all uploads were successful
    assert all(status_code == 202 for status_code in results), "Not all concurrent uploads were successful" 