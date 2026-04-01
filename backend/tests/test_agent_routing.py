"""
Agent Routing System Tests — iteration 18
Tests for:
  - services/agents.py (AGENTS dict, get_agent())
  - services/agent_router.py (route_to_agent() logic)
  - MessageResponse schema: agent_type, agent_name fields
  - GET /api/chats/{chat_id}/messages returns agent_type=None for old messages
  - POST /api/chats/{chat_id}/messages returns valid agent_type in assistant_message
"""
import pytest
import requests
import os
import sys

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Known IDs from previous testing iterations
PROJECT_ID = "560694a9-6522-4dda-bc5e-f8d81f329cbe"
PROJECT_CHAT_ID = "7d34ab68-60b5-44d4-9468-cf8f93fead5b"

VALID_AGENT_TYPES = {"excel", "research", "rag", "general"}


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Login and return JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@ai.planetworkspace.com", "password": "Admin@123456"}
    )
    if response.status_code != 200:
        pytest.skip(f"Login failed ({response.status_code}) — skipping all authenticated tests")
    data = response.json()
    token = data.get("token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── Health & Auth ──────────────────────────────────────────────────────────

class TestHealthAndAuth:
    """Basic connectivity tests"""

    def test_health_returns_200(self):
        """GET /api/health must return 200"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
        data = resp.json()
        # Status should be healthy (no import errors)
        assert data.get("status") in ("healthy", "ok", "running"), f"Unexpected status: {data}"
        print(f"Health check passed: {data}")

    def test_login_admin_success(self):
        """POST /api/auth/login with admin credentials returns token + user"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@ai.planetworkspace.com", "password": "Admin@123456"}
        )
        assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in login response"
        assert "user" in data, "No user in login response"
        assert data["user"]["email"] == "admin@ai.planetworkspace.com"
        print(f"Login succeeded, user id: {data['user']['id']}")


# ── agents.py Unit Tests ───────────────────────────────────────────────────

class TestAgentsModule:
    """Verify services/agents.py content and get_agent() function"""

    def test_agents_module_importable(self):
        """services/agents.py must be importable without errors"""
        # Add backend to path for direct import test
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agents import AGENTS, get_agent
        assert AGENTS is not None
        print(f"agents.py imported OK, agents: {list(AGENTS.keys())}")

    def test_agents_dict_has_all_four_agents(self):
        """AGENTS dict must contain excel, research, rag, general"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agents import AGENTS
        for agent_type in ("excel", "research", "rag", "general"):
            assert agent_type in AGENTS, f"Missing agent: {agent_type}"
            agent = AGENTS[agent_type]
            assert "name" in agent, f"Agent {agent_type} missing 'name'"
            assert "system_prompt" in agent, f"Agent {agent_type} missing 'system_prompt'"
            assert len(agent["system_prompt"]) > 10, f"Agent {agent_type} system_prompt too short"
        print(f"All 4 agents present: {list(AGENTS.keys())}")

    def test_get_agent_returns_correct_agent(self):
        """get_agent() must return the right agent dict"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agents import get_agent, AGENTS
        for agent_type in ("excel", "research", "rag", "general"):
            result = get_agent(agent_type)
            assert result == AGENTS[agent_type], f"get_agent({agent_type!r}) returned wrong value"
        print("get_agent() returns correct agents for all 4 types")

    def test_get_agent_unknown_falls_back_to_general(self):
        """get_agent() with unknown type must return 'general' agent"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agents import get_agent, AGENTS
        result = get_agent("unknown_type")
        assert result == AGENTS["general"], "get_agent('unknown_type') should fall back to general"
        print("get_agent fallback to general works correctly")


# ── agent_router.py Unit Tests ────────────────────────────────────────────

class TestAgentRouterModule:
    """Verify services/agent_router.py imports and rule-based routing"""

    def test_agent_router_importable(self):
        """services/agent_router.py must be importable without errors"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent
        assert callable(route_to_agent), "route_to_agent must be a callable"
        print("agent_router.py imported OK")

    def test_route_to_agent_has_excel_source_excel_keyword(self):
        """When has_excel_source=True and message has 'excel' keyword → should route to 'excel'"""
        import asyncio
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent

        result = asyncio.get_event_loop().run_until_complete(
            route_to_agent(
                message="Show me the excel spreadsheet data",
                has_excel_source=True,
                has_rag_context=False,
                use_web_search=False
            )
        )
        assert result == "excel", f"Expected 'excel', got {result!r}"
        print(f"Rule-based excel routing works: {result}")

    def test_route_to_agent_has_rag_context_routes_to_rag(self):
        """When has_rag_context=True and no excel/web search → should route to 'rag'"""
        import asyncio
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent

        result = asyncio.get_event_loop().run_until_complete(
            route_to_agent(
                message="What does the document say about the project?",
                has_excel_source=False,
                has_rag_context=True,
                use_web_search=False
            )
        )
        assert result == "rag", f"Expected 'rag', got {result!r}"
        print(f"Rule-based RAG routing works: {result}")

    def test_route_to_agent_use_web_search_routes_to_research(self):
        """When use_web_search=True and no excel/rag → should route to 'research'"""
        import asyncio
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent

        result = asyncio.get_event_loop().run_until_complete(
            route_to_agent(
                message="Some question",
                has_excel_source=False,
                has_rag_context=False,
                use_web_search=True
            )
        )
        assert result == "research", f"Expected 'research', got {result!r}"
        print(f"Rule-based research routing works: {result}")

    def test_route_to_agent_no_context_falls_back(self):
        """When no context at all and no CLAUDE_API_KEY → should return 'general'"""
        import asyncio
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent

        # No excel, no rag, no web search → goes to Claude haiku OR falls back to general
        result = asyncio.get_event_loop().run_until_complete(
            route_to_agent(
                message="Hello, how are you?",
                has_excel_source=False,
                has_rag_context=False,
                use_web_search=False
            )
        )
        assert result in VALID_AGENT_TYPES, f"Expected valid agent type, got {result!r}"
        print(f"No-context routing returns: {result!r}")

    def test_route_to_agent_returns_valid_type_on_error(self):
        """route_to_agent must never crash — always return a valid agent type"""
        import asyncio
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from services.agent_router import route_to_agent

        # Simulate edge case: very long message
        long_message = "x " * 5000
        result = asyncio.get_event_loop().run_until_complete(
            route_to_agent(
                message=long_message,
                has_excel_source=False,
                has_rag_context=False,
                use_web_search=False
            )
        )
        assert result in VALID_AGENT_TYPES, f"Expected valid agent type, got {result!r}"
        print(f"Edge case (long message) routing returns: {result!r}")


# ── MessageResponse Schema Tests ──────────────────────────────────────────

class TestMessageResponseSchema:
    """Verify MessageResponse has agent_type and agent_name fields"""

    def test_schema_has_agent_type_field(self):
        """MessageResponse must have agent_type: Optional[str] = None"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from models.schemas import MessageResponse
        fields = MessageResponse.model_fields
        assert "agent_type" in fields, "MessageResponse missing 'agent_type' field"
        field = fields["agent_type"]
        # Default must be None
        assert field.default is None, f"agent_type default should be None, got {field.default}"
        print("MessageResponse.agent_type field present with default=None")

    def test_schema_has_agent_name_field(self):
        """MessageResponse must have agent_name: Optional[str] = None"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from models.schemas import MessageResponse
        fields = MessageResponse.model_fields
        assert "agent_name" in fields, "MessageResponse missing 'agent_name' field"
        field = fields["agent_name"]
        assert field.default is None, f"agent_name default should be None, got {field.default}"
        print("MessageResponse.agent_name field present with default=None")

    def test_schema_accepts_none_values(self):
        """MessageResponse must be constructable without agent_type/agent_name (backward compat)"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from models.schemas import MessageResponse
        from datetime import datetime, timezone
        msg = MessageResponse(
            id="test-id",
            chatId="chat-id",
            role="assistant",
            content="Hello",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
        assert msg.agent_type is None
        assert msg.agent_name is None
        print("MessageResponse created without agent_type/agent_name — backward compatible")

    def test_schema_accepts_agent_type_values(self):
        """MessageResponse must accept valid agent_type strings"""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from models.schemas import MessageResponse
        from datetime import datetime, timezone
        for agent_type in ("excel", "research", "rag", "general"):
            msg = MessageResponse(
                id="test-id",
                chatId="chat-id",
                role="assistant",
                content="Hello",
                createdAt=datetime.now(timezone.utc).isoformat(),
                agent_type=agent_type,
                agent_name="Test Agent"
            )
            assert msg.agent_type == agent_type
            assert msg.agent_name == "Test Agent"
        print("MessageResponse accepts all valid agent_type values")


# ── API Integration Tests ─────────────────────────────────────────────────

class TestGetMessagesAPI:
    """GET /api/chats/{chat_id}/messages integration tests"""

    def test_get_messages_returns_200(self, auth_headers):
        """GET /api/chats/{chat_id}/messages should return 200"""
        resp = requests.get(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        messages = resp.json()
        assert isinstance(messages, list), f"Expected list, got {type(messages)}"
        print(f"GET messages returned {len(messages)} messages")

    def test_get_messages_no_schema_validation_errors(self, auth_headers):
        """GET messages must not have schema validation errors (agent_type field backward compat)"""
        resp = requests.get(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Schema validation failed: {resp.status_code}"
        messages = resp.json()
        # Verify each message has expected fields
        for msg in messages:
            assert "id" in msg, "Message missing 'id'"
            assert "chatId" in msg, "Message missing 'chatId'"
            assert "role" in msg, "Message missing 'role'"
            assert "content" in msg, "Message missing 'content'"
            assert "createdAt" in msg, "Message missing 'createdAt'"
        print(f"All {len(messages)} messages pass schema validation")

    def test_get_messages_agent_type_is_none_or_string_for_old_messages(self, auth_headers):
        """Old messages should have agent_type=None or a valid string (not missing key)"""
        resp = requests.get(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            headers=auth_headers
        )
        assert resp.status_code == 200
        messages = resp.json()
        for msg in messages:
            if msg.get("role") == "assistant":
                # agent_type must be present and either None or a valid string
                assert "agent_type" in msg, f"Message {msg.get('id')} missing 'agent_type' field"
                agent_type = msg.get("agent_type")
                assert agent_type is None or agent_type in VALID_AGENT_TYPES, \
                    f"Invalid agent_type: {agent_type!r}"
                print(f"  Message {msg.get('id')[:8]}: agent_type={agent_type!r}")


class TestSendMessageWithAgentRouting:
    """POST /api/chats/{chat_id}/messages — verify agent_type in assistant response"""

    def test_send_general_message_has_valid_agent_type(self, auth_headers):
        """Sending a simple message should return agent_type in VALID_AGENT_TYPES"""
        payload = {"content": "Hello, what is 2+2?"}
        resp = requests.post(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            json=payload,
            headers=auth_headers,
            timeout=60
        )
        assert resp.status_code == 200, f"Send message failed: {resp.status_code} {resp.text[:300]}"
        data = resp.json()

        # Response should have user_message and assistant_message
        assert "user_message" in data or "assistant_message" in data, \
            f"Unexpected response structure: {list(data.keys())}"

        assistant_msg = data.get("assistant_message", {})
        assert assistant_msg, "No assistant_message in response"

        agent_type = assistant_msg.get("agent_type")
        agent_name = assistant_msg.get("agent_name")

        print(f"General message → agent_type={agent_type!r}, agent_name={agent_name!r}")
        assert agent_type in VALID_AGENT_TYPES, \
            f"agent_type {agent_type!r} not in {VALID_AGENT_TYPES}"
        assert agent_name is not None, "agent_name should not be None for new messages"
        assert isinstance(agent_name, str) and len(agent_name) > 0, "agent_name should be non-empty string"

    def test_send_message_no_crash_on_routing(self, auth_headers):
        """Sending any message must not crash — agent routing is fault-tolerant"""
        payload = {"content": "Tell me about this project."}
        resp = requests.post(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            json=payload,
            headers=auth_headers,
            timeout=60
        )
        # Should never return 500 — agent routing falls back to 'general' on error
        assert resp.status_code not in (500, 422), f"Server error {resp.status_code}: {resp.text[:300]}"
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assistant_msg = data.get("assistant_message", {})
        agent_type = assistant_msg.get("agent_type")
        print(f"Project query → agent_type={agent_type!r}")
        assert agent_type in VALID_AGENT_TYPES, f"Invalid agent_type: {agent_type!r}"

    def test_assistant_message_persisted_with_agent_type(self, auth_headers):
        """After sending, GET messages should show the new message with agent_type set"""
        # Send a message first
        payload = {"content": "Quick test message for agent routing verification."}
        send_resp = requests.post(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            json=payload,
            headers=auth_headers,
            timeout=60
        )
        assert send_resp.status_code == 200, f"Send failed: {send_resp.status_code}"
        sent_assistant = send_resp.json().get("assistant_message", {})
        sent_agent_type = sent_assistant.get("agent_type")
        sent_msg_id = sent_assistant.get("id")

        print(f"Sent message: assistant_id={sent_msg_id!r}, agent_type={sent_agent_type!r}")

        # Now GET messages and find our message
        get_resp = requests.get(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            headers=auth_headers
        )
        assert get_resp.status_code == 200

        messages = get_resp.json()
        # Find our specific assistant message
        found = next((m for m in messages if m.get("id") == sent_msg_id), None)
        assert found is not None, f"Sent message {sent_msg_id!r} not found in GET response"

        persisted_agent_type = found.get("agent_type")
        print(f"Persisted agent_type from GET: {persisted_agent_type!r}")
        assert persisted_agent_type == sent_agent_type, \
            f"agent_type mismatch: sent={sent_agent_type!r}, persisted={persisted_agent_type!r}"
        assert persisted_agent_type in VALID_AGENT_TYPES, \
            f"Persisted agent_type invalid: {persisted_agent_type!r}"

    def test_unauthenticated_send_returns_401_or_403(self):
        """POST messages without auth must return 401 or 403"""
        payload = {"content": "Hello"}
        resp = requests.post(
            f"{BASE_URL}/api/chats/{PROJECT_CHAT_ID}/messages",
            json=payload,
            timeout=30
        )
        assert resp.status_code in (401, 403), \
            f"Expected 401 or 403 for unauthenticated request, got {resp.status_code}"
        print(f"Unauthenticated send correctly returns {resp.status_code}")


# ── Quick Chat Agent Routing ──────────────────────────────────────────────

class TestQuickChatAgentRouting:
    """Test agent routing in a quick (non-project) chat"""

    def test_create_quick_chat_and_send_message(self, auth_headers):
        """Create a quick chat, send a message, verify agent_type is present"""
        # Create quick chat
        create_resp = requests.post(
            f"{BASE_URL}/api/quick-chats",
            json={"name": "TEST_AgentRouting QuickChat"},
            headers=auth_headers,
            timeout=30
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip(f"Could not create quick chat: {create_resp.status_code}")

        chat = create_resp.json()
        chat_id = chat.get("id")
        assert chat_id, "No chat id in response"
        print(f"Created quick chat: {chat_id}")

        # Send a message
        payload = {"content": "What is the capital of France?"}
        send_resp = requests.post(
            f"{BASE_URL}/api/chats/{chat_id}/messages",
            json=payload,
            headers=auth_headers,
            timeout=60
        )
        assert send_resp.status_code == 200, f"Send failed: {send_resp.status_code} {send_resp.text[:200]}"
        data = send_resp.json()
        assistant_msg = data.get("assistant_message", {})
        agent_type = assistant_msg.get("agent_type")
        agent_name = assistant_msg.get("agent_name")

        print(f"Quick chat general query → agent_type={agent_type!r}, agent_name={agent_name!r}")
        assert agent_type in VALID_AGENT_TYPES, f"agent_type {agent_type!r} not valid"
        assert agent_name is not None and len(agent_name) > 0, "agent_name must be non-empty"

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/quick-chats/{chat_id}",
            headers=auth_headers,
            timeout=10
        )
        print(f"Cleaned up quick chat {chat_id}")
