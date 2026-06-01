import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
response = client.get("/api/v1/1/onboarding/policy-templates")
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
