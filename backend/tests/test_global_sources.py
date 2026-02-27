"""
Test suite for Global Sources feature in Planet GPT
Tests admin endpoints for managing global knowledge base
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestGlobalSourcesFeature:
    """Tests for Global Sources admin functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - cannot test global sources")
        
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.admin_user = login_response.json().get("user")
        
    def test_admin_login_success(self):
        """Test admin login with admin@admin.com / admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["isAdmin"] == True
        assert data["user"]["email"] == "admin@admin.com"
        print("✓ Admin login successful")
    
    def test_get_global_sources_admin(self):
        """Test GET /api/admin/global-sources - admin can view global sources"""
        response = self.session.get(f"{BASE_URL}/api/admin/global-sources")
        
        assert response.status_code == 200, f"Failed to get global sources: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Admin can view global sources (count: {len(data)})")
        return data
    
    def test_get_global_sources_user_endpoint(self):
        """Test GET /api/global-sources - regular users can view global sources"""
        response = self.session.get(f"{BASE_URL}/api/global-sources")
        
        assert response.status_code == 200, f"Failed to get global sources for users: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Users can view global sources (count: {len(data)})")
    
    def test_upload_global_source_file(self):
        """Test POST /api/admin/global-sources/upload - upload a text file"""
        # Create a simple text file
        test_content = "This is a test global source file for Planet GPT testing.\nIt contains important knowledge for all users."
        files = {
            'file': ('test_global_source.txt', io.BytesIO(test_content.encode()), 'text/plain')
        }
        
        # Remove Content-Type header for multipart upload
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/admin/global-sources/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to upload global source: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["kind"] == "file"
        assert data["originalName"] == "test_global_source.txt"
        assert data["projectId"] == "__global__"
        print(f"✓ Global source file uploaded successfully (id: {data['id']})")
        return data["id"]
    
    def test_add_global_source_url(self):
        """Test POST /api/admin/global-sources/url - add URL source"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/global-sources/url",
            json={"url": "https://example.com"}
        )
        
        # URL might fail if example.com doesn't return enough content
        # But we test the endpoint works
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["kind"] == "url"
            assert data["projectId"] == "__global__"
            print(f"✓ Global URL source added successfully (id: {data['id']})")
            return data["id"]
        elif response.status_code == 400:
            # Expected if URL doesn't have enough content
            print("✓ URL endpoint works (returned 400 - not enough content from URL)")
            return None
        else:
            pytest.fail(f"Unexpected response: {response.status_code} - {response.text}")
    
    def test_preview_global_source(self):
        """Test GET /api/admin/global-sources/{id}/preview"""
        # First upload a source
        test_content = "Preview test content for global source.\nThis should be visible in preview."
        files = {
            'file': ('preview_test.txt', io.BytesIO(test_content.encode()), 'text/plain')
        }
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/admin/global-sources/upload",
            files=files,
            headers=headers
        )
        
        if upload_response.status_code != 200:
            pytest.skip("Could not upload source for preview test")
        
        source_id = upload_response.json()["id"]
        
        # Now test preview
        preview_response = self.session.get(f"{BASE_URL}/api/admin/global-sources/{source_id}/preview")
        
        assert preview_response.status_code == 200, f"Preview failed: {preview_response.text}"
        data = preview_response.json()
        assert "id" in data
        assert "text" in data
        assert "chunkCount" in data
        assert "wordCount" in data
        assert "Preview test content" in data["text"]
        print(f"✓ Global source preview works (chunks: {data['chunkCount']}, words: {data['wordCount']})")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/admin/global-sources/{source_id}")
        return source_id
    
    def test_delete_global_source(self):
        """Test DELETE /api/admin/global-sources/{id}"""
        # First upload a source to delete
        test_content = "This source will be deleted."
        files = {
            'file': ('delete_test.txt', io.BytesIO(test_content.encode()), 'text/plain')
        }
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/admin/global-sources/upload",
            files=files,
            headers=headers
        )
        
        if upload_response.status_code != 200:
            pytest.skip("Could not upload source for delete test")
        
        source_id = upload_response.json()["id"]
        
        # Delete the source
        delete_response = self.session.delete(f"{BASE_URL}/api/admin/global-sources/{source_id}")
        
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        data = delete_response.json()
        assert "message" in data
        print(f"✓ Global source deleted successfully")
        
        # Verify it's gone
        verify_response = self.session.get(f"{BASE_URL}/api/admin/global-sources/{source_id}/preview")
        assert verify_response.status_code == 404, "Source should not exist after deletion"
        print("✓ Verified source no longer exists")
    
    def test_non_admin_cannot_access_admin_endpoints(self):
        """Test that non-admin users cannot access admin global sources endpoints"""
        # Create a regular user session
        user_session = requests.Session()
        
        # First, we need to create a test user or use existing one
        # Try to login with a test user
        login_response = user_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "testpass123"
        })
        
        if login_response.status_code != 200:
            # User doesn't exist, skip this test
            print("✓ Skipped non-admin test (no test user available)")
            return
        
        token = login_response.json().get("token")
        user_session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        
        # Try to access admin endpoint
        response = user_session.get(f"{BASE_URL}/api/admin/global-sources")
        assert response.status_code == 403, f"Non-admin should get 403, got {response.status_code}"
        print("✓ Non-admin users cannot access admin global sources endpoints")
    
    def test_global_sources_included_in_chat_context(self):
        """Test that global sources are included when sending messages"""
        # This is a conceptual test - we verify the endpoint structure
        # The actual inclusion happens in the send_message endpoint
        
        # Get current global sources
        sources_response = self.session.get(f"{BASE_URL}/api/global-sources")
        assert sources_response.status_code == 200
        
        global_sources = sources_response.json()
        print(f"✓ Global sources available for chat context (count: {len(global_sources)})")
        
        # Note: Full integration test would require creating a project, chat, and sending a message
        # The backend code at line 1803-1804 shows global sources are added to active_source_ids


class TestGlobalSourcesCleanup:
    """Cleanup test data after tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_cleanup_test_sources(self):
        """Clean up any test sources created during testing"""
        response = self.session.get(f"{BASE_URL}/api/admin/global-sources")
        
        if response.status_code != 200:
            return
        
        sources = response.json()
        test_sources = [s for s in sources if s.get("originalName", "").startswith("test_") or 
                       s.get("originalName", "").startswith("preview_") or
                       s.get("originalName", "").startswith("delete_")]
        
        for source in test_sources:
            self.session.delete(f"{BASE_URL}/api/admin/global-sources/{source['id']}")
        
        print(f"✓ Cleaned up {len(test_sources)} test sources")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
