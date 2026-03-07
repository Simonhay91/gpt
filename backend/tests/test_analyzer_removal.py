"""
Test Excel Analyzer Removal - Verify analyzer endpoints return 404
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnalyzerRemoval:
    """Verify Excel Analyzer feature has been completely removed"""
    
    def test_analyzer_upload_returns_404(self):
        """POST /api/analyzer/upload should return 404"""
        response = requests.post(f"{BASE_URL}/api/analyzer/upload")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: /api/analyzer/upload returns 404")
    
    def test_analyzer_ask_returns_404(self):
        """POST /api/analyzer/ask should return 404"""
        response = requests.post(f"{BASE_URL}/api/analyzer/ask", json={"session_id": "test", "question": "test"})
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: /api/analyzer/ask returns 404")
    
    def test_analyzer_session_returns_404(self):
        """GET /api/analyzer/session/{id} should return 404"""
        response = requests.get(f"{BASE_URL}/api/analyzer/session/test-session")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: /api/analyzer/session/{id} returns 404")
    
    def test_analyzer_export_excel_returns_404(self):
        """GET /api/analyzer/export/excel/{id} should return 404"""
        response = requests.get(f"{BASE_URL}/api/analyzer/export/excel/test-session")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: /api/analyzer/export/excel/{id} returns 404")
    
    def test_analyzer_export_pdf_returns_404(self):
        """GET /api/analyzer/export/pdf/{id} should return 404"""
        response = requests.get(f"{BASE_URL}/api/analyzer/export/pdf/test-session")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: /api/analyzer/export/pdf/{id} returns 404")


class TestCoreAPIsStillWork:
    """Verify core APIs still work after analyzer removal"""
    
    def test_health_endpoint(self):
        """GET /api/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: /api/health returns 200 with healthy status")
    
    def test_login_works(self):
        """POST /api/auth/login should work with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "admin@admin.com"
        print("PASS: Login works with admin@admin.com")
    
    def test_projects_endpoint_requires_auth(self):
        """GET /api/projects should require authentication"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code in [401, 403]
        print("PASS: /api/projects requires authentication")
    
    def test_projects_endpoint_with_auth(self):
        """GET /api/projects should work with valid token"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        token = login_response.json()["token"]
        
        # Get projects
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)
        print("PASS: /api/projects works with authentication")
    
    def test_quick_chats_endpoint(self):
        """GET /api/quick-chats should work with valid token"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        token = login_response.json()["token"]
        
        # Get quick chats
        response = requests.get(
            f"{BASE_URL}/api/quick-chats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("PASS: /api/quick-chats works with authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
