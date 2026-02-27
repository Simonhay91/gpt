"""
Enterprise Knowledge Architecture Tests
Tests for: Departments, Personal Sources, Source Versions, Audit Logs
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin123"
TEST_USER_ID = "0f280224-1be1-4d03-8ff5-753ea5b5545a"  # simon
EXISTING_DEPT_ID = "99d37445-1ebf-424c-8157-c38a7a93199a"  # Engineering


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def admin_user_id(admin_token):
    """Get admin user ID"""
    response = requests.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    return response.json()["id"]


class TestDepartments:
    """Department CRUD and member management tests"""
    
    created_dept_id = None
    
    def test_list_departments(self, admin_headers):
        """GET /api/departments - List all departments"""
        response = requests.get(f"{BASE_URL}/api/departments", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} departments")
    
    def test_create_department(self, admin_headers):
        """POST /api/departments - Create new department"""
        dept_name = f"TEST_Dept_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/departments", headers=admin_headers, json={
            "name": dept_name,
            "description": "Test department for automated testing"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["name"] == dept_name
        assert "id" in data
        TestDepartments.created_dept_id = data["id"]
        print(f"✓ Created department: {dept_name} (ID: {data['id']})")
    
    def test_create_department_without_name_fails(self, admin_headers):
        """POST /api/departments - Should fail without name"""
        response = requests.post(f"{BASE_URL}/api/departments", headers=admin_headers, json={
            "description": "No name provided"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Create department without name correctly rejected")
    
    def test_get_department_details(self, admin_headers):
        """GET /api/departments/{id} - Get department details"""
        if not TestDepartments.created_dept_id:
            pytest.skip("No department created")
        
        response = requests.get(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["id"] == TestDepartments.created_dept_id
        assert "members" in data
        assert "sourceCount" in data
        print(f"✓ Got department details: {data['name']}")
    
    def test_update_department(self, admin_headers):
        """PUT /api/departments/{id} - Update department"""
        if not TestDepartments.created_dept_id:
            pytest.skip("No department created")
        
        new_description = "Updated description for testing"
        response = requests.put(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}",
            headers=admin_headers,
            json={"description": new_description}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["description"] == new_description
        print(f"✓ Updated department description")
    
    def test_add_member_to_department(self, admin_headers):
        """POST /api/departments/{id}/members - Add member"""
        if not TestDepartments.created_dept_id:
            pytest.skip("No department created")
        
        # First get a user to add
        users_response = requests.get(f"{BASE_URL}/api/users/list", headers=admin_headers)
        if users_response.status_code != 200:
            pytest.skip("Cannot get users list")
        
        users = users_response.json()
        if len(users) < 2:
            pytest.skip("Not enough users to test member addition")
        
        # Find a non-admin user
        test_user = None
        for u in users:
            if not u["email"].endswith("@admin.com"):
                test_user = u
                break
        
        if not test_user:
            pytest.skip("No non-admin user found")
        
        response = requests.post(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}/members",
            headers=admin_headers,
            json={"userId": test_user["id"], "isManager": False}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "member" in data
        print(f"✓ Added member {test_user['email']} to department")
    
    def test_add_duplicate_member_fails(self, admin_headers):
        """POST /api/departments/{id}/members - Should fail for duplicate"""
        if not TestDepartments.created_dept_id:
            pytest.skip("No department created")
        
        # Get current members
        dept_response = requests.get(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}",
            headers=admin_headers
        )
        if dept_response.status_code != 200:
            pytest.skip("Cannot get department")
        
        members = dept_response.json().get("members", [])
        if not members:
            pytest.skip("No members to test duplicate")
        
        # Try to add existing member again
        response = requests.post(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}/members",
            headers=admin_headers,
            json={"userId": members[0]["userId"], "isManager": False}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Duplicate member correctly rejected")
    
    def test_get_nonexistent_department_fails(self, admin_headers):
        """GET /api/departments/{id} - Should fail for non-existent"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/departments/{fake_id}", headers=admin_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent department correctly returns 404")
    
    def test_delete_department(self, admin_headers):
        """DELETE /api/departments/{id} - Delete department"""
        if not TestDepartments.created_dept_id:
            pytest.skip("No department created")
        
        response = requests.delete(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ Deleted department {TestDepartments.created_dept_id}")
        
        # Verify deletion
        verify_response = requests.get(
            f"{BASE_URL}/api/departments/{TestDepartments.created_dept_id}",
            headers=admin_headers
        )
        assert verify_response.status_code == 404
        print("✓ Verified department deletion")


class TestPersonalSources:
    """Personal sources upload and management tests"""
    
    uploaded_source_id = None
    
    def test_list_personal_sources(self, admin_headers):
        """GET /api/personal-sources - List user's personal sources"""
        response = requests.get(f"{BASE_URL}/api/personal-sources", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} personal sources")
    
    def test_upload_personal_source(self, admin_headers):
        """POST /api/personal-sources/upload - Upload personal source"""
        # Create a test file
        test_content = """
        Test Personal Source Document
        
        This is a test document for the Enterprise Knowledge Architecture.
        It contains sample text that will be chunked and stored.
        
        Section 1: Introduction
        The personal sources feature allows users to upload private documents.
        
        Section 2: Features
        - Private storage
        - Version control
        - Publishing to projects/departments
        """
        
        files = {
            'file': ('test_personal_source.txt', test_content.encode(), 'text/plain')
        }
        headers = {"Authorization": admin_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/personal-sources/upload",
            headers=headers,
            files=files
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["level"] == "personal"
        assert "id" in data
        assert data["chunkCount"] > 0
        TestPersonalSources.uploaded_source_id = data["id"]
        print(f"✓ Uploaded personal source: {data['originalName']} ({data['chunkCount']} chunks)")
    
    def test_upload_empty_file_fails(self, admin_headers):
        """POST /api/personal-sources/upload - Should fail for empty file"""
        files = {
            'file': ('empty.txt', b'', 'text/plain')
        }
        headers = {"Authorization": admin_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/personal-sources/upload",
            headers=headers,
            files=files
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Empty file upload correctly rejected")
    
    def test_upload_unsupported_file_type_fails(self, admin_headers):
        """POST /api/personal-sources/upload - Should fail for unsupported type"""
        files = {
            'file': ('test.exe', b'binary content', 'application/octet-stream')
        }
        headers = {"Authorization": admin_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/personal-sources/upload",
            headers=headers,
            files=files
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Unsupported file type correctly rejected")


class TestSourceVersions:
    """Source versioning tests"""
    
    def test_get_source_versions(self, admin_headers):
        """GET /api/sources/{id}/versions - Get source versions"""
        if not TestPersonalSources.uploaded_source_id:
            pytest.skip("No source uploaded")
        
        response = requests.get(
            f"{BASE_URL}/api/sources/{TestPersonalSources.uploaded_source_id}/versions",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least initial version
        
        # Check version structure
        if data:
            version = data[0]
            assert "version" in version
            assert "contentHash" in version
            assert "createdAt" in version
            print(f"✓ Got {len(data)} version(s) for source")
    
    def test_get_versions_nonexistent_source(self, admin_headers):
        """GET /api/sources/{id}/versions - Should fail for non-existent"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/sources/{fake_id}/versions", headers=admin_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent source versions correctly returns 404")


class TestPublishSource:
    """Personal source publishing tests"""
    
    def test_publish_to_project(self, admin_headers, admin_user_id):
        """POST /api/personal-sources/{id}/publish - Publish to project"""
        if not TestPersonalSources.uploaded_source_id:
            pytest.skip("No source uploaded")
        
        # First get a project to publish to
        projects_response = requests.get(f"{BASE_URL}/api/projects", headers=admin_headers)
        if projects_response.status_code != 200:
            pytest.skip("Cannot get projects")
        
        projects = projects_response.json()
        if not projects:
            # Create a test project
            create_response = requests.post(
                f"{BASE_URL}/api/projects",
                headers=admin_headers,
                json={"name": "TEST_PublishProject"}
            )
            if create_response.status_code != 200:
                pytest.skip("Cannot create test project")
            projects = [create_response.json()]
        
        target_project = projects[0]
        
        response = requests.post(
            f"{BASE_URL}/api/personal-sources/{TestPersonalSources.uploaded_source_id}/publish",
            headers=admin_headers,
            json={
                "targetLevel": "project",
                "targetId": target_project["id"]
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "source" in data
        assert data["source"]["level"] == "project"
        print(f"✓ Published source to project: {target_project['name']}")
    
    def test_publish_invalid_target_fails(self, admin_headers):
        """POST /api/personal-sources/{id}/publish - Should fail for invalid target"""
        if not TestPersonalSources.uploaded_source_id:
            pytest.skip("No source uploaded")
        
        response = requests.post(
            f"{BASE_URL}/api/personal-sources/{TestPersonalSources.uploaded_source_id}/publish",
            headers=admin_headers,
            json={
                "targetLevel": "invalid_level",
                "targetId": "some-id"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid publish target correctly rejected")


class TestAuditLogs:
    """Audit logging tests"""
    
    def test_get_audit_logs(self, admin_headers):
        """GET /api/admin/audit-logs - Get audit logs (admin)"""
        response = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} audit log entries")
    
    def test_get_audit_logs_with_filters(self, admin_headers):
        """GET /api/admin/audit-logs - With filters"""
        # Test entity filter
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?entity=department",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # All returned logs should be for department entity
        for log in data:
            assert log.get("entity") == "department" or len(data) == 0
        print(f"✓ Filtered audit logs by entity: {len(data)} entries")
    
    def test_get_audit_logs_with_action_filter(self, admin_headers):
        """GET /api/admin/audit-logs - Filter by action"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=create",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        for log in data:
            assert log.get("action") == "create" or len(data) == 0
        print(f"✓ Filtered audit logs by action: {len(data)} entries")
    
    def test_get_audit_logs_with_limit(self, admin_headers):
        """GET /api/admin/audit-logs - With limit"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=5",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert len(data) <= 5
        print(f"✓ Limited audit logs: {len(data)} entries (max 5)")
    
    def test_audit_log_structure(self, admin_headers):
        """Verify audit log entry structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=1",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data:
            log = data[0]
            # Check required fields
            assert "id" in log
            assert "entity" in log
            assert "action" in log
            assert "userId" in log
            assert "userEmail" in log
            assert "timestamp" in log
            print(f"✓ Audit log structure verified")
        else:
            print("✓ No audit logs to verify structure (empty)")


class TestCleanup:
    """Cleanup test data"""
    
    def test_delete_personal_source(self, admin_headers):
        """DELETE /api/personal-sources/{id} - Delete test source"""
        if not TestPersonalSources.uploaded_source_id:
            pytest.skip("No source to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/personal-sources/{TestPersonalSources.uploaded_source_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ Deleted test personal source")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
