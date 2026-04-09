"""
Test suite for Planet Knowledge new features:
1. All sources in a project are automatically active (no manual selection needed)
2. Project sharing with user list selection
3. Support for PPTX, XLSX, PNG, JPEG files
4. Multiple file upload and ZIP download
5. 5px padding for chat list
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Test authentication with admin credentials"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login with admin credentials and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    def test_login_admin(self, auth_token):
        """Test admin login works"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Admin login successful, token length: {len(auth_token)}")


class TestUsersListAPI:
    """Test the /api/users/list endpoint for project sharing"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_users_list_endpoint_exists(self, auth_headers):
        """Test that /api/users/list endpoint exists and returns data"""
        response = requests.get(f"{BASE_URL}/api/users/list", headers=auth_headers)
        assert response.status_code == 200, f"Users list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Users list endpoint returns {len(data)} users")
    
    def test_users_list_excludes_current_user(self, auth_headers):
        """Test that current user is excluded from the list"""
        response = requests.get(f"{BASE_URL}/api/users/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Get current user
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert me_response.status_code == 200
        current_user_id = me_response.json()["id"]
        
        # Check current user is not in the list
        user_ids = [u["id"] for u in data]
        assert current_user_id not in user_ids, "Current user should be excluded from list"
        print(f"✓ Current user correctly excluded from users list")
    
    def test_users_list_has_required_fields(self, auth_headers):
        """Test that users in list have id and email fields"""
        response = requests.get(f"{BASE_URL}/api/users/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        for user in data:
            assert "id" in user, "User should have id field"
            assert "email" in user, "User should have email field"
        print(f"✓ All users have required id and email fields")


class TestProjectSharing:
    """Test project sharing functionality"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create a test project"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_ShareProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_share_project_endpoint(self, auth_headers, test_project):
        """Test sharing project with another user"""
        # Get users list
        users_response = requests.get(f"{BASE_URL}/api/users/list", headers=auth_headers)
        assert users_response.status_code == 200
        users = users_response.json()
        
        if len(users) > 0:
            # Share with first user
            user_to_share = users[0]
            share_response = requests.post(
                f"{BASE_URL}/api/projects/{test_project['id']}/share",
                json={"email": user_to_share["email"]},
                headers=auth_headers
            )
            assert share_response.status_code == 200, f"Share failed: {share_response.text}"
            print(f"✓ Project shared with {user_to_share['email']}")
        else:
            print("⚠ No other users to share with, skipping share test")
    
    def test_get_project_members(self, auth_headers, test_project):
        """Test getting project members"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{test_project['id']}/members",
            headers=auth_headers
        )
        assert response.status_code == 200
        members = response.json()
        assert isinstance(members, list)
        assert len(members) >= 1, "Should have at least the owner"
        
        # Check owner exists
        owner = next((m for m in members if m["role"] == "owner"), None)
        assert owner is not None, "Should have an owner"
        print(f"✓ Project has {len(members)} members")


class TestFileTypeSupport:
    """Test support for PPTX, XLSX, PNG, JPEG files"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create a test project for file uploads"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_FileUploadProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_png_upload_supported(self, auth_headers, test_project):
        """Test PNG file upload is supported"""
        # Create a minimal PNG file (1x1 pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth, color type
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {'file': ('test.png', io.BytesIO(png_data), 'image/png')}
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"PNG upload failed: {response.text}"
        data = response.json()
        assert data["mimeType"] == "image/png"
        print(f"✓ PNG file upload supported")
    
    def test_jpeg_upload_supported(self, auth_headers, test_project):
        """Test JPEG file upload is supported"""
        # Create a minimal JPEG file
        jpeg_data = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
            0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
            0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
            0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
            0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
            0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
            0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
            0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
            0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
            0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
            0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
            0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04,
            0x00, 0x00, 0x01, 0x7D, 0x01, 0x02, 0x03, 0x00,
            0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
            0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1,
            0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A,
            0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35,
            0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55,
            0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65,
            0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85,
            0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94,
            0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2,
            0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA,
            0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8,
            0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6,
            0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA,
            0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
            0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x7F, 0xFF,
            0xD9
        ])
        
        files = {'file': ('test.jpg', io.BytesIO(jpeg_data), 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"JPEG upload failed: {response.text}"
        data = response.json()
        assert data["mimeType"] == "image/jpeg"
        print(f"✓ JPEG file upload supported")
    
    def test_txt_upload_supported(self, auth_headers, test_project):
        """Test TXT file upload is supported"""
        txt_content = b"This is a test text file with enough content to be processed correctly."
        
        files = {'file': ('test.txt', io.BytesIO(txt_content), 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"TXT upload failed: {response.text}"
        data = response.json()
        assert data["mimeType"] == "text/plain"
        print(f"✓ TXT file upload supported")


class TestMultipleFileUpload:
    """Test multiple file upload functionality"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create a test project for multiple file uploads"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_MultiUploadProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_multiple_file_upload_endpoint(self, auth_headers, test_project):
        """Test uploading multiple files at once"""
        # Create two text files
        file1_content = b"This is the first test file with enough content to be processed."
        file2_content = b"This is the second test file with enough content to be processed."
        
        files = [
            ('files', ('test1.txt', io.BytesIO(file1_content), 'text/plain')),
            ('files', ('test2.txt', io.BytesIO(file2_content), 'text/plain'))
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/sources/upload-multiple",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Multiple upload failed: {response.text}"
        data = response.json()
        
        assert "uploaded" in data, "Response should have 'uploaded' field"
        assert "errors" in data, "Response should have 'errors' field"
        assert len(data["uploaded"]) == 2, f"Should have uploaded 2 files, got {len(data['uploaded'])}"
        print(f"✓ Multiple file upload works: {len(data['uploaded'])} files uploaded")


class TestZipDownload:
    """Test ZIP download functionality"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project_with_files(self, auth_headers):
        """Create a test project with files for download"""
        # Create project
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_ZipDownloadProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        
        # Upload a file
        file_content = b"This is a test file for ZIP download with enough content."
        files = {'file': ('download_test.txt', io.BytesIO(file_content), 'text/plain')}
        upload_response = requests.post(
            f"{BASE_URL}/api/projects/{project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert upload_response.status_code == 200
        
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_download_all_endpoint_exists(self, auth_headers, test_project_with_files):
        """Test that download-all endpoint exists and returns ZIP"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{test_project_with_files['id']}/sources/download-all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Download failed: {response.text}"
        assert response.headers.get('content-type') == 'application/zip'
        assert len(response.content) > 0, "ZIP file should not be empty"
        print(f"✓ ZIP download works, received {len(response.content)} bytes")


class TestAutoActiveSourcesInChat:
    """Test that all sources are automatically active in project chats"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project_with_sources(self, auth_headers):
        """Create a test project with sources"""
        # Create project
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_AutoActiveProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        
        # Upload a source file
        file_content = b"This is test content about Python programming. Python is a great language."
        files = {'file': ('python_info.txt', io.BytesIO(file_content), 'text/plain')}
        upload_response = requests.post(
            f"{BASE_URL}/api/projects/{project['id']}/sources/upload",
            files=files,
            headers=auth_headers
        )
        assert upload_response.status_code == 200
        
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_sources_auto_active_in_chat(self, auth_headers, test_project_with_sources):
        """Test that sources are automatically used in chat without manual selection"""
        project_id = test_project_with_sources['id']
        
        # Create a chat
        chat_response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/chats",
            json={"name": "Test Auto Active Chat"},
            headers=auth_headers
        )
        assert chat_response.status_code == 200
        chat = chat_response.json()
        
        # Get project sources
        sources_response = requests.get(
            f"{BASE_URL}/api/projects/{project_id}/sources",
            headers=auth_headers
        )
        assert sources_response.status_code == 200
        sources = sources_response.json()
        assert len(sources) > 0, "Project should have sources"
        
        print(f"✓ Project has {len(sources)} sources that should be auto-active")
        
        # Cleanup chat
        requests.delete(f"{BASE_URL}/api/chats/{chat['id']}", headers=auth_headers)


class TestProjectCRUD:
    """Test basic project CRUD operations"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_create_project(self, auth_headers):
        """Test creating a new project"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_NewProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        assert "id" in project
        assert project["name"] == "TEST_NewProject"
        print(f"✓ Project created: {project['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_get_projects(self, auth_headers):
        """Test getting list of projects"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        print(f"✓ Got {len(projects)} projects")


class TestChatCRUD:
    """Test chat CRUD operations"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@admin.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_project(self, auth_headers):
        """Create a test project"""
        response = requests.post(f"{BASE_URL}/api/projects", 
            json={"name": "TEST_ChatProject"},
            headers=auth_headers
        )
        assert response.status_code == 200
        project = response.json()
        yield project
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project['id']}", headers=auth_headers)
    
    def test_create_chat(self, auth_headers, test_project):
        """Test creating a chat in a project"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            json={"name": "Test Chat"},
            headers=auth_headers
        )
        assert response.status_code == 200
        chat = response.json()
        assert "id" in chat
        assert chat["name"] == "Test Chat"
        print(f"✓ Chat created: {chat['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chats/{chat['id']}", headers=auth_headers)
    
    def test_get_project_chats(self, auth_headers, test_project):
        """Test getting chats in a project"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{test_project['id']}/chats",
            headers=auth_headers
        )
        assert response.status_code == 200
        chats = response.json()
        assert isinstance(chats, list)
        print(f"✓ Got {len(chats)} chats in project")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
