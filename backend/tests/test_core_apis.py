"""
Test suite for Planet Knowledge Core APIs:
- Health endpoint
- Authentication (login)
- Projects CRUD
- Chats CRUD
- Messages
- Sources
- Save to Knowledge
- Excel Analyzer
- Source mode toggle
"""
import pytest
import requests
import os
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin123"
MANAGER_EMAIL = "manager@test.com"
MANAGER_PASSWORD = "testpassword"


class TestHealthEndpoint:
    """Test /api/health endpoint"""
    
    def test_health_returns_200(self):
        """Health endpoint should return 200 with status healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        assert "timestamp" in data, "Missing timestamp in health response"
        print(f"✓ Health endpoint OK: {data['status']}")


class TestAuthentication:
    """Test /api/auth/* endpoints"""
    
    def test_login_admin_success(self):
        """Admin login should succeed with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Missing token in login response"
        assert "user" in data, "Missing user in login response"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["isAdmin"] == True
        print(f"✓ Admin login successful")
    
    def test_login_invalid_credentials(self):
        """Login should fail with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Invalid credentials correctly rejected")
    
    def test_auth_me_with_token(self):
        """GET /api/auth/me should return current user info"""
        # First login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["token"]
        
        # Get current user
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"✓ Auth me endpoint works")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me should fail without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Auth me correctly requires token")


class TestProjectsCRUD:
    """Test /api/projects/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_projects_list(self, auth_headers):
        """GET /api/projects should return list of projects"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Get projects failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Projects should be a list"
        print(f"✓ Get projects returns {len(data)} projects")
    
    def test_create_project(self, auth_headers):
        """POST /api/projects should create a new project"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_CoreAPIProject"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create project failed: {response.text}"
        data = response.json()
        assert "id" in data, "Missing id in project response"
        assert data["name"] == "TEST_CoreAPIProject"
        assert "ownerId" in data
        assert "createdAt" in data
        print(f"✓ Project created: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{data['id']}", headers=auth_headers)
    
    def test_get_project_by_id(self, auth_headers):
        """GET /api/projects/{id} should return project details"""
        # Create project first
        create_response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_GetProjectById"},
            headers=auth_headers
        )
        project_id = create_response.json()["id"]
        
        # Get project
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get project failed: {response.text}"
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "TEST_GetProjectById"
        print(f"✓ Get project by ID works")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_delete_project(self, auth_headers):
        """DELETE /api/projects/{id} should delete project"""
        # Create project
        create_response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_DeleteProject"},
            headers=auth_headers
        )
        project_id = create_response.json()["id"]
        
        # Delete project
        response = requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete project failed: {response.text}"
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert get_response.status_code == 404, "Project should be deleted"
        print(f"✓ Delete project works")
    
    def test_project_not_found(self, auth_headers):
        """GET /api/projects/{invalid_id} should return 404"""
        response = requests.get(f"{BASE_URL}/api/projects/invalid-uuid-12345", headers=auth_headers)
        assert response.status_code in [404, 403], f"Expected 404/403, got {response.status_code}"
        print(f"✓ Invalid project ID returns 404/403")


class TestChatsCRUD:
    """Test /api/chats/* and /api/projects/{id}/chats/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create a test project for chat tests"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_ChatTestProject"},
            headers=auth_headers
        )
        project = response.json()
        yield project
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_create_project_chat(self, auth_headers, test_project):
        """POST /api/projects/{id}/chats should create chat"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            json={"name": "Test Chat"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create chat failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Chat"
        assert data["projectId"] == test_project["id"]
        print(f"✓ Project chat created: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{data['id']}", headers=auth_headers)
    
    def test_get_project_chats(self, auth_headers, test_project):
        """GET /api/projects/{id}/chats should return chats list"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get chats failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get project chats returns {len(data)} chats")
    
    def test_get_chat_by_id(self, auth_headers, test_project):
        """GET /api/chats/{id} should return chat details"""
        # Create chat
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            json={"name": "Test Get Chat"},
            headers=auth_headers
        )
        chat_id = create_response.json()["id"]
        
        # Get chat
        response = requests.get(f"{BASE_URL}/api/chats/{chat_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get chat failed: {response.text}"
        data = response.json()
        assert data["id"] == chat_id
        print(f"✓ Get chat by ID works")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{chat_id}", headers=auth_headers)
    
    def test_delete_chat(self, auth_headers, test_project):
        """DELETE /api/chats/{id} should delete chat"""
        # Create chat
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            json={"name": "Test Delete Chat"},
            headers=auth_headers
        )
        chat_id = create_response.json()["id"]
        
        # Delete chat
        response = requests.delete(f"{BASE_URL}/api/chats/{chat_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete chat failed: {response.text}"
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/chats/{chat_id}", headers=auth_headers)
        assert get_response.status_code == 404
        print(f"✓ Delete chat works")
    
    def test_rename_chat(self, auth_headers, test_project):
        """PUT /api/chats/{id}/rename should rename chat"""
        # Create chat
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            json={"name": "Original Name"},
            headers=auth_headers
        )
        chat_id = create_response.json()["id"]
        
        # Rename chat
        response = requests.put(
            f"{BASE_URL}/api/chats/{chat_id}/rename",
            json={"name": "Renamed Chat"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Rename chat failed: {response.text}"
        data = response.json()
        assert data["name"] == "Renamed Chat"
        print(f"✓ Rename chat works")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{chat_id}", headers=auth_headers)


class TestQuickChats:
    """Test /api/quick-chats/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_create_quick_chat(self, auth_headers):
        """POST /api/quick-chats should create quick chat"""
        response = requests.post(
            f"{BASE_URL}/api/quick-chats",
            json={"name": "Test Quick Chat"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create quick chat failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["projectId"] is None  # Quick chats have no project
        print(f"✓ Quick chat created: {data['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{data['id']}", headers=auth_headers)
    
    def test_get_quick_chats(self, auth_headers):
        """GET /api/quick-chats should return quick chats list"""
        response = requests.get(f"{BASE_URL}/api/quick-chats", headers=auth_headers)
        assert response.status_code == 200, f"Get quick chats failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get quick chats returns {len(data)} chats")


class TestSourceModeToggle:
    """Test source mode toggle in chats"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project_with_chat(self, auth_headers):
        """Create project with chat for source mode tests"""
        # Create project
        project_response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_SourceModeProject"},
            headers=auth_headers
        )
        project = project_response.json()
        
        # Create chat
        chat_response = requests.post(
            f"{BASE_URL}/api/projects/{project['id']}/chats",
            json={"name": "Source Mode Test Chat"},
            headers=auth_headers
        )
        chat = chat_response.json()
        
        yield {"project": project, "chat": chat}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{chat['id']}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_update_source_mode(self, auth_headers, test_project_with_chat):
        """PUT /api/chats/{id}/source-mode should update source mode"""
        chat_id = test_project_with_chat["chat"]["id"]
        
        # Update to 'my' mode
        response = requests.put(
            f"{BASE_URL}/api/chats/{chat_id}/source-mode",
            json={"sourceMode": "my"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update source mode failed: {response.text}"
        data = response.json()
        assert data.get("sourceMode") == "my"
        print(f"✓ Source mode updated to 'my'")
        
        # Update back to 'all' mode
        response = requests.put(
            f"{BASE_URL}/api/chats/{chat_id}/source-mode",
            json={"sourceMode": "all"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("sourceMode") == "all"
        print(f"✓ Source mode updated to 'all'")


class TestSourcesUpload:
    """Test /api/projects/{id}/sources/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create test project for source tests"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_SourcesProject"},
            headers=auth_headers
        )
        project = response.json()
        yield project
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_upload_txt_source(self, auth_headers, test_project):
        """POST /api/projects/{id}/sources/upload should upload TXT file"""
        file_content = b"This is test content for source upload. It has enough text to be processed correctly by the system."
        files = {'file': ('test_source.txt', io.BytesIO(file_content), 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Upload source failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["kind"] == "file"
        assert data["mimeType"] == "text/plain"
        assert data["chunkCount"] > 0
        print(f"✓ TXT source uploaded: {data['id']} with {data['chunkCount']} chunks")
    
    def test_get_project_sources(self, auth_headers, test_project):
        """GET /api/projects/{id}/sources should return sources list"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get sources failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get project sources returns {len(data)} sources")
    
    def test_upload_url_source(self, auth_headers, test_project):
        """POST /api/projects/{id}/sources/url should add URL source"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/url",
            json={"url": "https://example.com"},
            headers=auth_headers
        )
        # URL source may fail if site is unreachable, but endpoint should exist
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ URL source endpoint exists (status: {response.status_code})")


class TestMessages:
    """Test /api/chats/{id}/messages/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_chat(self, auth_headers):
        """Create test chat for message tests"""
        # Create project
        project_response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_MessagesProject"},
            headers=auth_headers
        )
        project = project_response.json()
        
        # Create chat
        chat_response = requests.post(
            f"{BASE_URL}/api/projects/{project['id']}/chats",
            json={"name": "Messages Test Chat"},
            headers=auth_headers
        )
        chat = chat_response.json()
        
        yield {"project": project, "chat": chat}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{chat['id']}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_get_chat_messages(self, auth_headers, test_chat):
        """GET /api/chats/{id}/messages should return messages list"""
        chat_id = test_chat["chat"]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/chats/{chat_id}/messages",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get messages failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get chat messages returns {len(data)} messages")
    
    def test_send_message(self, auth_headers, test_chat):
        """POST /api/chats/{id}/messages should send message and get AI response"""
        chat_id = test_chat["chat"]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/chats/{chat_id}/messages",
            json={"content": "Hello, this is a test message"},
            headers=auth_headers,
            timeout=60  # AI response may take time
        )
        assert response.status_code == 200, f"Send message failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["role"] == "assistant"  # Response is from AI
        assert "content" in data
        print(f"✓ Message sent and AI response received")


class TestSaveToKnowledge:
    """Test /api/save-to-knowledge endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create test project"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_SaveToKnowledgeProject"},
            headers=auth_headers
        )
        project = response.json()
        yield project
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_save_to_knowledge_endpoint(self, auth_headers, test_project):
        """POST /api/save-to-knowledge should save content as source"""
        response = requests.post(
            f"{BASE_URL}/api/save-to-knowledge",
            json={
                "projectId": test_project["id"],
                "content": "This is important knowledge that should be saved for future reference. It contains valuable information about the project.",
                "title": "Test Knowledge Entry"
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Save to knowledge failed: {response.text}"
        data = response.json()
        assert "id" in data or "sourceId" in data or "message" in data
        print(f"✓ Save to knowledge endpoint works")


class TestExcelAnalyzer:
    """Test /api/analyzer/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_analyzer_upload_csv(self, auth_headers):
        """POST /api/analyzer/upload should upload CSV for analysis"""
        csv_content = b"Name,Age,City\nJohn,30,New York\nJane,25,Los Angeles\nBob,35,Chicago"
        files = {'file': ('test_data.csv', io.BytesIO(csv_content), 'text/csv')}
        
        response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Analyzer upload failed: {response.text}"
        data = response.json()
        assert "sessionId" in data or "session_id" in data or "id" in data
        print(f"✓ Analyzer upload works")
        
        # Return session ID for cleanup
        return data.get("sessionId") or data.get("session_id") or data.get("id")
    
    def test_analyzer_upload_invalid_file(self, auth_headers):
        """POST /api/analyzer/upload should reject invalid file types"""
        invalid_content = b"This is not a valid CSV or Excel file"
        files = {'file': ('test.xyz', io.BytesIO(invalid_content), 'application/octet-stream')}
        
        response = requests.post(
            f"{BASE_URL}/api/analyzer/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for invalid file, got {response.status_code}"
        print(f"✓ Analyzer correctly rejects invalid files")
    
    def test_analyzer_ask_nonexistent_session(self, auth_headers):
        """POST /api/analyzer/ask should return 404 for non-existent session"""
        response = requests.post(
            f"{BASE_URL}/api/analyzer/ask",
            json={
                "sessionId": "nonexistent-session-id",
                "question": "What is the average age?"
            },
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Analyzer ask returns 404 for invalid session")


class TestGlobalSources:
    """Test /api/global-sources/* endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_global_sources(self, auth_headers):
        """GET /api/global-sources should return global sources list"""
        response = requests.get(f"{BASE_URL}/api/global-sources", headers=auth_headers)
        assert response.status_code == 200, f"Get global sources failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get global sources returns {len(data)} sources")


class TestAdminEndpoints:
    """Test /api/admin/* endpoints (admin only)"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_admin_get_users(self, admin_headers):
        """GET /api/admin/users should return users list for admin"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200, f"Admin get users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin get users returns {len(data)} users")
    
    def test_admin_get_config(self, admin_headers):
        """GET /api/admin/config should return GPT config"""
        response = requests.get(f"{BASE_URL}/api/admin/config", headers=admin_headers)
        assert response.status_code == 200, f"Admin get config failed: {response.text}"
        data = response.json()
        assert "model" in data
        assert "developerPrompt" in data
        print(f"✓ Admin get config works, model: {data['model']}")
    
    def test_admin_source_stats(self, admin_headers):
        """GET /api/admin/source-stats should return source statistics"""
        response = requests.get(f"{BASE_URL}/api/admin/source-stats", headers=admin_headers)
        assert response.status_code == 200, f"Admin source stats failed: {response.text}"
        data = response.json()
        print(f"✓ Admin source stats works")
    
    def test_admin_cache_stats(self, admin_headers):
        """GET /api/admin/cache/stats should return cache statistics"""
        response = requests.get(f"{BASE_URL}/api/admin/cache/stats", headers=admin_headers)
        assert response.status_code == 200, f"Admin cache stats failed: {response.text}"
        data = response.json()
        print(f"✓ Admin cache stats works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
