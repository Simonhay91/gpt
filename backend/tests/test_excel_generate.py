"""
Backend tests for Excel Generation (excel-generate) and in-chat auto-detection.
Tests:
  - POST /api/chats/{chat_id}/excel-generate endpoint
  - In-chat auto-detection via POST /api/chats/{chat_id}/messages
  - Non-Excel messages do NOT trigger Excel generation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@ai.planetworkspace.com"
ADMIN_PASSWORD = "Admin@123456"

TEST_CHAT_ID = "84597c00-3098-401c-a26f-4729b36f240c"
TEST_SOURCE_ID = "a1e65d63-8537-47ce-bd53-90e4da27efd5"
TEST_PROJECT_ID = "24db323f-ce93-47ce-b45a-d4807a4cdeb4"

FAKE_SOURCE_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, f"'token' not in response: {data}"
    print(f"\nAuth token obtained: {data['token'][:20]}...")
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return Authorization headers"""
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================================
# Tests for POST /api/chats/{chat_id}/excel-generate
# ============================================================

class TestExcelGenerateEndpoint:
    """Tests for POST /api/chats/{chat_id}/excel-generate"""

    def test_excel_generate_requires_auth(self):
        """401 without auth token"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            json={"instruction": "Rename columns", "source_id": TEST_SOURCE_ID}
        )
        assert response.status_code in (401, 403), \
            f"Expected 401/403, got {response.status_code}: {response.text[:200]}"
        print("PASS: excel-generate requires auth")

    def test_excel_generate_missing_instruction(self, auth_headers):
        """400 when instruction is missing"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            headers=auth_headers,
            json={"source_id": TEST_SOURCE_ID}
        )
        assert response.status_code == 400, \
            f"Expected 400 for missing instruction, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert "instruction" in data.get("detail", "").lower(), \
            f"Error message should mention 'instruction': {data}"
        print("PASS: 400 for missing instruction")

    def test_excel_generate_missing_source_id(self, auth_headers):
        """400 when source_id is missing"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            headers=auth_headers,
            json={"instruction": "Rename columns"}
        )
        assert response.status_code == 400, \
            f"Expected 400 for missing source_id, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert "source_id" in data.get("detail", "").lower(), \
            f"Error message should mention 'source_id': {data}"
        print("PASS: 400 for missing source_id")

    def test_excel_generate_nonexistent_source(self, auth_headers):
        """404 for non-existent source_id"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            headers=auth_headers,
            json={"instruction": "Rename columns", "source_id": FAKE_SOURCE_ID}
        )
        assert response.status_code == 404, \
            f"Expected 404 for non-existent source_id, got {response.status_code}: {response.text[:200]}"
        print("PASS: 404 for non-existent source_id")

    def test_excel_generate_success(self, auth_headers):
        """Full success: returns message, file_id, rows, columns, preview_columns, preview"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            headers=auth_headers,
            json={
                "instruction": "Rename column 'name' to 'Имя', 'age' to 'Возраст', 'city' to 'Город'",
                "source_id": TEST_SOURCE_ID
            }
        )
        assert response.status_code == 200, \
            f"excel-generate failed: {response.status_code} - {response.text[:400]}"
        data = response.json()

        # Required fields
        assert "message" in data, f"Missing 'message' field: {data}"
        assert "file_id" in data, f"Missing 'file_id' field: {data}"
        assert "rows" in data, f"Missing 'rows' field: {data}"
        assert "columns" in data, f"Missing 'columns' field: {data}"
        assert "preview_columns" in data, f"Missing 'preview_columns' field: {data}"
        assert "preview" in data, f"Missing 'preview' field: {data}"

        # Type checks
        assert isinstance(data["message"], str) and len(data["message"]) > 0, "message must be non-empty string"
        assert isinstance(data["file_id"], str) and len(data["file_id"]) > 0, "file_id must be non-empty string"
        assert isinstance(data["rows"], int) and data["rows"] >= 0, f"rows must be int >= 0, got {data['rows']}"
        assert isinstance(data["columns"], int) and data["columns"] >= 0, f"columns must be int >= 0"
        assert isinstance(data["preview_columns"], list) and len(data["preview_columns"]) > 0, \
            f"preview_columns must be non-empty list"
        assert isinstance(data["preview"], list), "preview must be a list"
        assert len(data["preview"]) <= 5, f"preview should have at most 5 rows, got {len(data['preview'])}"

        # Validate data integrity: 3 rows, 3 columns (name, age, city)
        assert data["rows"] == 3, f"Expected 3 rows from test.csv, got {data['rows']}"
        assert data["columns"] == 3, f"Expected 3 columns, got {data['columns']}"

        print(f"PASS: excel-generate success")
        print(f"  message: {data['message']}")
        print(f"  file_id: {data['file_id']}")
        print(f"  rows: {data['rows']}, columns: {data['columns']}")
        print(f"  preview_columns: {data['preview_columns']}")
        print(f"  preview rows count: {len(data['preview'])}")

    def test_excel_generate_file_downloadable(self, auth_headers):
        """Generated file should be downloadable via /api/excel/download/{file_id}"""
        # First generate
        gen_resp = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-generate",
            headers=auth_headers,
            json={
                "instruction": "Add a new column 'greeting' with value 'Hello'",
                "source_id": TEST_SOURCE_ID
            }
        )
        assert gen_resp.status_code == 200, f"Generate step failed: {gen_resp.text[:200]}"
        file_id = gen_resp.json()["file_id"]
        print(f"  Generated file_id: {file_id}")

        # Download
        dl_resp = requests.get(
            f"{BASE_URL}/api/excel/download/{file_id}",
            headers=auth_headers
        )
        assert dl_resp.status_code == 200, \
            f"Download failed: {dl_resp.status_code} - {dl_resp.text[:200]}"
        content_type = dl_resp.headers.get("content-type", "")
        assert "spreadsheetml" in content_type or "application/octet-stream" in content_type, \
            f"Unexpected content-type: {content_type}"
        assert len(dl_resp.content) > 1000, f"File too small: {len(dl_resp.content)} bytes"
        print(f"PASS: Downloaded file ({len(dl_resp.content)} bytes, content-type: {content_type})")


# ============================================================
# Tests for in-chat auto-detection
# ============================================================

class TestInChatExcelDetection:
    """Test Excel auto-detection in POST /api/chats/{chat_id}/messages"""

    def test_excel_keyword_triggers_detection(self, auth_headers):
        """Message with Excel keyword + active CSV source returns excel_file_id and excel_preview"""
        # Send message with an Excel keyword that matches EXCEL_KEYWORDS list
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/messages",
            headers=auth_headers,
            json={"content": "переведи колонки таблицы csv на русский язык"}
        )
        assert response.status_code == 200, \
            f"send_message failed: {response.status_code} - {response.text[:400]}"
        data = response.json()

        # Response must contain both excel fields
        assert "excel_file_id" in data, f"Missing 'excel_file_id' in response: {list(data.keys())}"
        assert "excel_preview" in data, f"Missing 'excel_preview' in response: {list(data.keys())}"

        # excel_file_id should be non-null
        assert data["excel_file_id"] is not None, \
            f"excel_file_id is None (auto-detection did not trigger): {data}"

        # excel_preview should have structure
        assert data["excel_preview"] is not None, "excel_preview is None"
        assert "columns" in data["excel_preview"], f"Missing 'columns' in excel_preview: {data['excel_preview']}"
        assert "rows" in data["excel_preview"], f"Missing 'rows' in excel_preview: {data['excel_preview']}"
        assert "total_rows" in data["excel_preview"], f"Missing 'total_rows' in excel_preview: {data['excel_preview']}"
        assert "message" in data["excel_preview"], f"Missing 'message' in excel_preview: {data['excel_preview']}"

        assert isinstance(data["excel_preview"]["columns"], list) and len(data["excel_preview"]["columns"]) > 0, \
            "excel_preview.columns should be non-empty list"

        print(f"PASS: In-chat auto-detection triggered for Excel keyword message")
        print(f"  excel_file_id: {data['excel_file_id']}")
        print(f"  columns: {data['excel_preview']['columns']}")
        print(f"  total_rows: {data['excel_preview']['total_rows']}")

    def test_non_excel_message_no_detection(self, auth_headers):
        """Generic message (no Excel keyword) does NOT trigger Excel generation"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/messages",
            headers=auth_headers,
            json={"content": "привет, расскажи о себе"}
        )
        assert response.status_code == 200, \
            f"send_message failed: {response.status_code} - {response.text[:400]}"
        data = response.json()

        # excel_file_id should be null or absent
        file_id = data.get("excel_file_id")
        assert file_id is None, \
            f"Non-Excel message should NOT trigger generation, but excel_file_id={file_id}"

        print("PASS: Non-Excel message does NOT trigger Excel generation")

    def test_download_keyword_triggers_detection(self, auth_headers):
        """Message with 'скачать' keyword triggers Excel generation"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/messages",
            headers=auth_headers,
            json={"content": "скачать данные из таблицы"}
        )
        assert response.status_code == 200, \
            f"send_message failed: {response.status_code} - {response.text[:400]}"
        data = response.json()

        assert "excel_file_id" in data, f"Missing 'excel_file_id' key in response"
        assert data["excel_file_id"] is not None, \
            "excel_file_id should not be None for 'скачать' keyword"

        print(f"PASS: 'скачать' keyword triggers Excel generation: file_id={data['excel_file_id']}")

    def test_excel_keyword_english_triggers_detection(self, auth_headers):
        """English 'excel' keyword also triggers detection"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/messages",
            headers=auth_headers,
            json={"content": "generate excel from the data"}
        )
        assert response.status_code == 200, \
            f"send_message failed: {response.status_code} - {response.text[:400]}"
        data = response.json()

        assert "excel_file_id" in data, "Missing 'excel_file_id' key"
        assert data["excel_file_id"] is not None, \
            "Excel keyword 'excel' should trigger generation"

        print(f"PASS: English 'excel' keyword triggers generation: file_id={data['excel_file_id']}")
