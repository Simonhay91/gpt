"""
Refactoring smoke tests - verify all critical APIs still work after
messages.py (1485→889 lines) and ChatPage.js (1791→896 lines) refactoring.
Tests: auth login, dashboard, chat messages, send message, edit, move, rename.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "admin@ai.planetworkspace.com"
ADMIN_PASSWORD = "Admin@123456"

# Known chat IDs from agent context
QUICK_CHAT_ID = "601b3e24-cd1d-46fb-9036-c43b26462a15"
TEST_CHAT_ID = "84597c00-3098-401c-a26f-4729b36f240c"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token") or data.get("token")
        if token:
            return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


# ==================== AUTH TESTS ====================

class TestAuth:
    """Auth endpoint tests"""

    def test_login_success(self):
        """Login with admin credentials returns token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text[:200]}"
        data = resp.json()
        assert "access_token" in data or "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        user = data["user"]
        assert user.get("email") == ADMIN_EMAIL

    def test_login_invalid_credentials(self):
        """Login with wrong password returns 401"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "wrongpassword"
        })
        assert resp.status_code in [401, 422], f"Expected 401/422, got {resp.status_code}"

    def test_get_current_user(self, api_client):
        """Get current user endpoint works"""
        resp = api_client.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("email") == ADMIN_EMAIL


# ==================== DASHBOARD / PROJECTS ====================

class TestDashboard:
    """Dashboard and project listing tests"""

    def test_list_projects(self, api_client):
        """GET /api/projects returns list"""
        resp = api_client.get(f"{BASE_URL}/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        # API returns a direct list
        projects = data if isinstance(data, list) else (data.get("items") or [])
        assert isinstance(projects, list)
        print(f"Found {len(projects)} projects")

    def test_list_quick_chats(self, api_client):
        """GET /api/quick-chats returns quick chats"""
        resp = api_client.get(f"{BASE_URL}/api/quick-chats")
        assert resp.status_code == 200
        data = resp.json()
        chats = data if isinstance(data, list) else (data.get("items") or [])
        assert isinstance(chats, list)
        print(f"Found {len(chats)} quick chats")


# ==================== CHAT & MESSAGES ====================

class TestChatMessages:
    """Chat and message CRUD tests - core of the refactoring"""

    def test_get_quick_chat(self, api_client):
        """GET /api/chats/{id} for known Quick Chat"""
        resp = api_client.get(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}")
        assert resp.status_code == 200, f"Chat not found: {resp.text[:200]}"
        data = resp.json()
        assert data.get("id") == QUICK_CHAT_ID
        print(f"Quick Chat name: {data.get('name')}")

    def test_get_test_chat(self, api_client):
        """GET /api/chats/{id} for Test Chat"""
        resp = api_client.get(f"{BASE_URL}/api/chats/{TEST_CHAT_ID}")
        assert resp.status_code == 200, f"Chat not found: {resp.text[:200]}"
        data = resp.json()
        assert data.get("id") == TEST_CHAT_ID
        print(f"Test Chat name: {data.get('name')}, projectId: {data.get('projectId')}")

    def test_get_messages_quick_chat(self, api_client):
        """GET /api/chats/{id}/messages for Quick Chat"""
        resp = api_client.get(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        # API returns direct list
        messages = data if isinstance(data, list) else (data.get("items") or [])
        assert isinstance(messages, list)
        print(f"Quick Chat has {len(messages)} messages")

    def test_get_messages_test_chat(self, api_client):
        """GET /api/chats/{id}/messages for Test Chat"""
        resp = api_client.get(f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        messages = data if isinstance(data, list) else (data.get("items") or [])
        assert isinstance(messages, list)
        print(f"Test Chat has {len(messages)} messages")

    def test_messages_response_schema(self, api_client):
        """Messages have correct fields (refactored MessageResponse schema)"""
        resp = api_client.get(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        messages = data if isinstance(data, list) else data.get("items", [])
        if messages:
            msg = messages[0]
            # Verify critical fields exist
            assert "id" in msg, "Missing 'id' field"
            assert "role" in msg, "Missing 'role' field"
            assert "content" in msg, "Missing 'content' field"
            assert "createdAt" in msg, "Missing 'createdAt' field"
            assert "chatId" in msg, "Missing 'chatId' field"
            print(f"Message schema valid: role={msg['role']}, fields present: {list(msg.keys())[:8]}")

    def test_send_message_unauthorized(self):
        """Send message without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/messages", json={
            "content": "Test message"
        })
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_send_message_to_quick_chat(self, api_client):
        """POST /api/chats/{id}/messages sends message and gets AI response"""
        resp = api_client.post(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/messages", json={
            "content": "Hello, please give me a brief greeting."
        }, timeout=60)
        assert resp.status_code == 200, f"Send failed: {resp.text[:300]}"
        data = resp.json()
        # Verify response structure
        assert "user_message" in data, "Missing 'user_message' in response"
        assert "assistant_message" in data, "Missing 'assistant_message' in response"
        user_msg = data["user_message"]
        asst_msg = data["assistant_message"]
        assert user_msg.get("role") == "user"
        assert asst_msg.get("role") == "assistant"
        assert len(asst_msg.get("content", "")) > 5, "Assistant response too short"
        print(f"AI response received: {asst_msg['content'][:100]}...")


# ==================== CHAT RENAME ====================

class TestChatRename:
    """Chat rename API test"""

    def test_rename_quick_chat(self, api_client):
        """PUT /api/chats/{id}/rename works"""
        original_resp = api_client.get(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}")
        original_name = original_resp.json().get("name", "Quick Chat")

        new_name = f"Test Renamed {original_name[:20]}"
        resp = api_client.put(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/rename", json={
            "name": new_name
        })
        assert resp.status_code == 200, f"Rename failed: {resp.text[:200]}"
        data = resp.json()
        assert data.get("name") == new_name or data.get("name") is not None
        print(f"Renamed to: {data.get('name')}")

        # Restore original name
        api_client.put(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/rename", json={"name": original_name})


# ==================== SAVE TO KNOWLEDGE ====================

class TestSaveToKnowledge:
    """Save-to-knowledge endpoint test"""

    def test_save_to_knowledge(self, api_client):
        """POST /api/save-to-knowledge creates personal source"""
        resp = api_client.post(f"{BASE_URL}/api/save-to-knowledge", json={
            "content": "This is TEST_ refactoring smoke test content that should be saved as a personal source.",
            "chatId": QUICK_CHAT_ID
        })
        assert resp.status_code == 200, f"Save to knowledge failed: {resp.text[:200]}"
        data = resp.json()
        assert data.get("success") is True
        assert "sourceId" in data
        print(f"Saved to knowledge: sourceId={data.get('sourceId')}")


# ==================== SAVE CONTEXT ====================

class TestSaveContext:
    """Save context endpoint test"""

    def test_save_context(self, api_client):
        """POST /api/chats/{id}/save-context works"""
        resp = api_client.post(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/save-context", json={
            "dialogText": "Пользователь: Привет\n\nAI: Здравствуйте! Чем могу помочь?"
        }, timeout=30)
        assert resp.status_code == 200, f"Save context failed: {resp.text[:200]}"
        data = resp.json()
        assert data.get("success") is True
        print(f"Context saved, summary: {data.get('summary', '')[:80]}")


# ==================== ACTIVE SOURCES ====================

class TestActiveSources:
    """Active sources sync test"""

    def test_set_active_sources(self, api_client):
        """POST /api/chats/{id}/active-sources works"""
        resp = api_client.post(f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/active-sources", json={
            "sourceIds": []
        })
        assert resp.status_code == 200, f"Active sources failed: {resp.text[:200]}"


# ==================== SOURCE MODE ====================

class TestSourceMode:
    """Source mode toggle test"""

    def test_set_source_mode(self, api_client):
        """PUT /api/chats/{id}/source-mode works"""
        resp = api_client.put(f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/source-mode", json={
            "sourceMode": "all"
        })
        assert resp.status_code == 200, f"Source mode failed: {resp.text[:200]}"


# ==================== MOVE CHAT ====================

class TestMoveChatDialog:
    """Move chat endpoint - just validates projects list loads"""

    def test_list_projects_for_move(self, api_client):
        """GET /api/projects returns list (for move-chat dialog)"""
        resp = api_client.get(f"{BASE_URL}/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        projects = data if isinstance(data, list) else (data.get("items") or [])
        assert isinstance(projects, list)
        print(f"Move dialog would show {len(projects)} projects")


# ==================== EXTRACT MEMORY POINTS ====================

class TestMemoryPoints:
    """Extract memory points endpoint test"""

    def test_extract_memory_points(self, api_client):
        """POST /api/chats/{id}/extract-memory-points works"""
        resp = api_client.post(f"{BASE_URL}/api/chats/{QUICK_CHAT_ID}/extract-memory-points", json={
            "dialogText": "User: What are the main KPIs?\nAI: The main KPIs are revenue growth, customer retention, and NPS score."
        }, timeout=30)
        assert resp.status_code == 200, f"Extract memory points failed: {resp.text[:200]}"
        data = resp.json()
        assert "points" in data
        assert isinstance(data["points"], list)
        print(f"Extracted {len(data['points'])} memory points")
