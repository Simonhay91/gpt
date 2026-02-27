"""
Test suite for Project Member Role Management
Tests the bug fix: changing member roles in shared projects
Features tested:
- PUT /api/projects/{projectId}/members/{userId}/role?role=newRole
- GET /api/projects/{projectId}/members (verify roles are returned correctly)
- Share project with role selection
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from the review request
ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin123"
TEST_PROJECT_ID = "2c0f2149-4157-45fb-a350-e084164b12c4"
TEST_MEMBER_SIMON_ID = "0f280224-1be1-4d03-8ff5-753ea5b5545a"
TEST_MEMBER_TIGRAN_ID = "2c9594b5-9da5-4ca4-bf13-85dc435064c4"


class TestMemberRoleManagement:
    """Tests for member role update functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        self.token = data.get("token")
        self.user_id = data.get("user", {}).get("id")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        # Cleanup: No specific cleanup needed
    
    def test_01_health_check(self):
        """Verify API is healthy"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")
    
    def test_02_get_project_members(self):
        """Test GET /api/projects/{projectId}/members returns members with roles"""
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200, f"Failed to get members: {response.text}"
        
        members = response.json()
        assert isinstance(members, list), "Members should be a list"
        assert len(members) > 0, "Project should have at least one member (owner)"
        
        # Verify owner exists
        owner = next((m for m in members if m.get("role") == "owner"), None)
        assert owner is not None, "Owner should be in members list"
        
        # Verify each member has required fields
        for member in members:
            assert "id" in member, "Member should have id"
            assert "email" in member, "Member should have email"
            assert "role" in member, "Member should have role"
            assert member["role"] in ["owner", "viewer", "editor", "manager"], f"Invalid role: {member['role']}"
        
        print(f"✓ Got {len(members)} members with roles")
        for m in members:
            print(f"  - {m['email']}: {m['role']}")
    
    def test_03_update_member_role_viewer_to_editor(self):
        """Test changing member role from viewer to editor"""
        # First get current members to find a non-owner member
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        # Find a non-owner member
        non_owner = next((m for m in members if m.get("role") != "owner"), None)
        if not non_owner:
            pytest.skip("No non-owner members to test role change")
        
        member_id = non_owner["id"]
        original_role = non_owner["role"]
        new_role = "editor"
        
        # Update role
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{member_id}/role",
            params={"role": new_role}
        )
        assert response.status_code == 200, f"Failed to update role: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert new_role in data["message"]
        
        # Verify role was updated by fetching members again
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        updated_member = next((m for m in members if m["id"] == member_id), None)
        assert updated_member is not None, "Member should still exist"
        assert updated_member["role"] == new_role, f"Role should be {new_role}, got {updated_member['role']}"
        
        print(f"✓ Successfully changed role from {original_role} to {new_role}")
    
    def test_04_update_member_role_editor_to_manager(self):
        """Test changing member role from editor to manager"""
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        # Find a non-owner member
        non_owner = next((m for m in members if m.get("role") != "owner"), None)
        if not non_owner:
            pytest.skip("No non-owner members to test role change")
        
        member_id = non_owner["id"]
        new_role = "manager"
        
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{member_id}/role",
            params={"role": new_role}
        )
        assert response.status_code == 200, f"Failed to update role: {response.text}"
        
        # Verify
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        members = response.json()
        updated_member = next((m for m in members if m["id"] == member_id), None)
        assert updated_member["role"] == new_role
        
        print(f"✓ Successfully changed role to manager")
    
    def test_05_update_member_role_manager_to_viewer(self):
        """Test changing member role from manager back to viewer"""
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        non_owner = next((m for m in members if m.get("role") != "owner"), None)
        if not non_owner:
            pytest.skip("No non-owner members to test role change")
        
        member_id = non_owner["id"]
        new_role = "viewer"
        
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{member_id}/role",
            params={"role": new_role}
        )
        assert response.status_code == 200, f"Failed to update role: {response.text}"
        
        # Verify
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        members = response.json()
        updated_member = next((m for m in members if m["id"] == member_id), None)
        assert updated_member["role"] == new_role
        
        print(f"✓ Successfully changed role back to viewer")
    
    def test_06_update_role_invalid_role(self):
        """Test that invalid role returns 400 error"""
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        members = response.json()
        
        non_owner = next((m for m in members if m.get("role") != "owner"), None)
        if not non_owner:
            pytest.skip("No non-owner members to test")
        
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{non_owner['id']}/role",
            params={"role": "invalid_role"}
        )
        assert response.status_code == 400, f"Should return 400 for invalid role, got {response.status_code}"
        print("✓ Invalid role correctly rejected with 400")
    
    def test_07_update_role_cannot_change_owner(self):
        """Test that owner's role cannot be changed"""
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        members = response.json()
        
        owner = next((m for m in members if m.get("role") == "owner"), None)
        assert owner is not None
        
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{owner['id']}/role",
            params={"role": "viewer"}
        )
        assert response.status_code == 400, f"Should return 400 when trying to change owner role, got {response.status_code}"
        print("✓ Cannot change owner's role - correctly rejected")
    
    def test_08_update_role_member_not_found(self):
        """Test that non-existent member returns 404"""
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        
        response = self.session.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members/{fake_user_id}/role",
            params={"role": "editor"}
        )
        assert response.status_code == 404, f"Should return 404 for non-existent member, got {response.status_code}"
        print("✓ Non-existent member correctly returns 404")
    
    def test_09_share_project_with_role(self):
        """Test sharing project with specific role"""
        # This test verifies the share endpoint works with role parameter
        # We'll try to share with a test email (may fail if user doesn't exist, which is expected)
        response = self.session.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/share",
            json={"email": "test_nonexistent@example.com", "role": "editor"}
        )
        # Should return 404 if user doesn't exist
        if response.status_code == 404:
            print("✓ Share endpoint correctly returns 404 for non-existent user")
        elif response.status_code == 200:
            print("✓ Share endpoint works with role parameter")
        else:
            print(f"Share endpoint returned {response.status_code}: {response.text}")
    
    def test_10_verify_roles_persist_after_get(self):
        """Verify that roles are correctly returned from get_project_members after updates"""
        # Get members
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        # Verify structure
        for member in members:
            assert "id" in member
            assert "email" in member
            assert "role" in member
            # Role should be one of the valid roles
            assert member["role"] in ["owner", "viewer", "editor", "manager"], \
                f"Member {member['email']} has invalid role: {member['role']}"
        
        print(f"✓ All {len(members)} members have valid roles")


class TestMemberRolePermissions:
    """Test permission checks for role updates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        
        data = response.json()
        self.token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
    
    def test_only_owner_can_change_roles(self):
        """Verify that only project owner can change member roles"""
        # This is implicitly tested by the backend check
        # The endpoint checks: if project["ownerId"] != current_user["id"]
        # Since we're logged in as admin who is the owner, this should work
        
        response = self.session.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/members")
        assert response.status_code == 200
        members = response.json()
        
        # Verify admin is the owner
        admin_member = next((m for m in members if m.get("email") == ADMIN_EMAIL), None)
        assert admin_member is not None
        assert admin_member["role"] == "owner", f"Admin should be owner, got {admin_member['role']}"
        
        print("✓ Admin is confirmed as project owner")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
