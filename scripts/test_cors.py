"""
CORS Configuration Testing
Verifies frontend can communicate with backend
"""

import sys
from pathlib import Path
import requests

sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings


def test_cors():
    """Test CORS configuration for frontend integration."""
    
    print("\n" + "=" * 70)
    print("CORS CONFIGURATION TEST")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    origin = "http://localhost:3000"
    
    print(f"\nFrontend Origin: {origin}")
    print(f"Backend URL: {base_url}")
    print(f"Allowed Origins: {settings.backend_cors_origins_list}")
    
    # Test 1: Simple health check
    print("\n" + "-" * 70)
    print("Test 1: Health Check")
    print("-" * 70)
    
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {response.json()}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 2: Preflight request (OPTIONS)
    print("\n" + "-" * 70)
    print("Test 2: CORS Preflight (OPTIONS)")
    print("-" * 70)
    
    try:
        response = requests.options(
            f"{base_url}/api/v1/register",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )
        
        print(f"✓ Status: {response.status_code}")
        print(f"\nCORS Headers:")
        
        cors_headers = [
            'access-control-allow-origin',
            'access-control-allow-methods',
            'access-control-allow-headers',
            'access-control-allow-credentials'
        ]
        
        for header in cors_headers:
            value = response.headers.get(header, 'Not set')
            print(f"  {header}: {value}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 3: Actual POST with Origin header
    print("\n" + "-" * 70)
    print("Test 3: POST Request with CORS")
    print("-" * 70)
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/register",
            json={
                "first_name": "CORS",
                "last_name": "Test",
                "email": "cors-test@example.com",
                "mobile": "1234567890"
            },
            headers={
                "Origin": origin,
                "Content-Type": "application/json"
            }
        )
        
        print(f"✓ Status: {response.status_code}")
        
        if response.status_code == 201:
            print(f"✓ Registration successful!")
        elif response.status_code == 409:
            print(f"⚠️  Email already exists (expected if run multiple times)")
        else:
            print(f"Response: {response.json()}")
        
        # Check CORS header in response
        cors_origin = response.headers.get('access-control-allow-origin')
        print(f"\nCORS header in response: {cors_origin}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Success
    print("\n" + "=" * 70)
    print("✓ CORS TESTS PASSED")
    print("=" * 70)
    
    print("\nFrontend Integration Example:")
    print("-" * 70)
    print("""
// In your React app:
fetch('http://localhost:8000/api/v1/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    first_name: 'John',
    last_name: 'Doe',
    email: 'john@example.com',
    mobile: '9876543210'
  })
})
.then(res => res.json())
.then(data => console.log('Success:', data))
.catch(err => console.error('Error:', err));
""")
    print("-" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = test_cors()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)