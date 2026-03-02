"""
Test Excel/CSV Analyzer API endpoints
Tests: /api/analyzer/upload, /api/analyzer/ask, /api/analyzer/session
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnalyzerAPI:
    """Excel/CSV Analyzer endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Authentication failed - skipping tests")
        
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.analysis_session_id = None
        
        yield
        
        # Cleanup - delete session if created
        if self.analysis_session_id:
            try:
                self.session.delete(f"{BASE_URL}/api/analyzer/session/{self.analysis_session_id}")
            except:
                pass
    
    def test_upload_csv_file(self):
        """Test uploading a CSV file for analysis"""
        # Create test CSV content
        csv_content = "Имя,Отдел,Зарплата,Возраст\nИван Петров,IT,85000,28\nМария Сидорова,HR,65000,35\nАлексей Козлов,IT,90000,32\nЕлена Новикова,Finance,75000,29"
        
        files = {
            'file': ('test_data.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        # Remove Content-Type header for multipart upload
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=headers
        )
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response: {response.text[:500] if response.text else 'empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "file_name" in data, "Response should contain file_name"
        assert "columns" in data, "Response should contain columns"
        assert "total_rows" in data, "Response should contain total_rows"
        assert "preview" in data, "Response should contain preview"
        
        # Verify columns
        assert len(data["columns"]) == 4, f"Expected 4 columns, got {len(data['columns'])}"
        assert data["total_rows"] == 4, f"Expected 4 rows, got {data['total_rows']}"
        
        # Store session_id for cleanup and further tests
        self.analysis_session_id = data["session_id"]
        print(f"Session created: {self.analysis_session_id}")
        
        return data["session_id"]
    
    def test_upload_invalid_file_type(self):
        """Test uploading an invalid file type (should fail)"""
        files = {
            'file': ('test.txt', io.BytesIO(b'plain text content'), 'text/plain')
        }
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=headers
        )
        
        print(f"Invalid file upload response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400 for invalid file type, got {response.status_code}"
    
    def test_ask_question_about_data(self):
        """Test asking a question about uploaded data"""
        # First upload a file
        csv_content = "Name,Department,Salary,Age\nJohn,IT,85000,28\nMary,HR,65000,35\nAlex,IT,90000,32"
        
        files = {
            'file': ('employees.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=headers
        )
        
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        session_id = upload_response.json()["session_id"]
        self.analysis_session_id = session_id
        
        # Now ask a question
        ask_response = self.session.post(f"{BASE_URL}/api/analyzer/ask", json={
            "session_id": session_id,
            "question": "How many employees are in the IT department?"
        })
        
        print(f"Ask response status: {ask_response.status_code}")
        print(f"Ask response: {ask_response.text[:500] if ask_response.text else 'empty'}")
        
        assert ask_response.status_code == 200, f"Expected 200, got {ask_response.status_code}: {ask_response.text}"
        
        data = ask_response.json()
        assert "answer" in data, "Response should contain answer"
        assert "session_id" in data, "Response should contain session_id"
        assert len(data["answer"]) > 0, "Answer should not be empty"
        
        print(f"AI Answer: {data['answer'][:200]}...")
    
    def test_ask_without_session(self):
        """Test asking a question without a valid session (should fail)"""
        response = self.session.post(f"{BASE_URL}/api/analyzer/ask", json={
            "session_id": "non-existent-session-id",
            "question": "What is the total salary?"
        })
        
        print(f"Ask without session response: {response.status_code}")
        assert response.status_code == 404, f"Expected 404 for non-existent session, got {response.status_code}"
    
    def test_get_session_info(self):
        """Test getting session information"""
        # First upload a file
        csv_content = "Product,Price,Quantity\nApple,1.50,100\nBanana,0.75,200"
        
        files = {
            'file': ('products.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=headers
        )
        
        assert upload_response.status_code == 200
        session_id = upload_response.json()["session_id"]
        self.analysis_session_id = session_id
        
        # Get session info
        session_response = self.session.get(f"{BASE_URL}/api/analyzer/session/{session_id}")
        
        print(f"Get session response: {session_response.status_code}")
        assert session_response.status_code == 200, f"Expected 200, got {session_response.status_code}"
        
        data = session_response.json()
        assert "session_id" in data
        assert "file_name" in data
        assert "columns" in data
        assert "total_rows" in data
        assert "messages" in data
    
    def test_delete_session(self):
        """Test deleting an analysis session"""
        # First upload a file
        csv_content = "A,B,C\n1,2,3\n4,5,6"
        
        files = {
            'file': ('temp.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=headers
        )
        
        assert upload_response.status_code == 200
        session_id = upload_response.json()["session_id"]
        
        # Delete session
        delete_response = self.session.delete(f"{BASE_URL}/api/analyzer/session/{session_id}")
        
        print(f"Delete session response: {delete_response.status_code}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        # Verify session is deleted
        get_response = self.session.get(f"{BASE_URL}/api/analyzer/session/{session_id}")
        assert get_response.status_code == 404, "Session should be deleted"
        
        # Clear session_id since we already deleted it
        self.analysis_session_id = None
    
    def test_upload_without_auth(self):
        """Test uploading without authentication (should fail)"""
        csv_content = "A,B\n1,2"
        
        files = {
            'file': ('test.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        
        # No auth header
        response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files
        )
        
        print(f"Upload without auth response: {response.status_code}")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
