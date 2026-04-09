"""
Backend tests for Excel/CSV Assistant feature
Tests: POST /api/chats/{chat_id}/excel-process and GET /api/excel/download/{file_id}
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@ai.planetworkspace.com"
ADMIN_PASSWORD = "Admin@123456"

# Test project/chat IDs from context
TEST_CHAT_ID = "84597c00-3098-401c-a26f-4729b36f240c"

# CSV content for testing
TEST_CSV_CONTENT = b"name,age,city\nAlice,30,Moscow\nBob,25,Paris\nCharlie,35,London\n"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token using admin credentials"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, "Missing 'token' in login response"
    print(f"Auth token obtained successfully")
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with Authorization token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestExcelProcessEndpoint:
    """Tests for POST /api/chats/{chat_id}/excel-process"""

    def test_excel_process_requires_auth(self):
        """Should return 401/403 without auth token"""
        csv_buf = io.BytesIO(TEST_CSV_CONTENT)
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            files={"file": ("test.csv", csv_buf, "text/csv")},
            data={"instruction": "Rename column name to Имя"}
        )
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"
        print("PASS: /excel-process requires authentication")

    def test_excel_process_csv_success(self, auth_headers):
        """Should process CSV and return message, download_url, preview_columns, preview"""
        csv_buf = io.BytesIO(TEST_CSV_CONTENT)
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            files={"file": ("test.csv", csv_buf, "text/csv")},
            data={"instruction": "Rename column 'name' to 'Имя', 'age' to 'Возраст', 'city' to 'Город'"}
        )
        assert response.status_code == 200, f"Excel process failed: {response.status_code} - {response.text[:300]}"
        data = response.json()

        # Validate response structure
        assert "message" in data, "Missing 'message' in response"
        assert "download_url" in data, "Missing 'download_url' in response"
        assert "rows" in data, "Missing 'rows' in response"
        assert "columns" in data, "Missing 'columns' in response"
        assert "preview_columns" in data, "Missing 'preview_columns' in response"
        assert "preview" in data, "Missing 'preview' in response"

        # Validate data types
        assert isinstance(data["message"], str) and len(data["message"]) > 0, "message should be non-empty string"
        assert isinstance(data["download_url"], str), "download_url should be a string"
        assert data["download_url"].startswith("/api/excel/download/"), f"download_url format invalid: {data['download_url']}"
        assert isinstance(data["rows"], int) and data["rows"] == 3, f"Expected 3 rows, got {data['rows']}"
        assert isinstance(data["columns"], int) and data["columns"] == 3, f"Expected 3 columns, got {data['columns']}"
        assert isinstance(data["preview_columns"], list) and len(data["preview_columns"]) == 3, \
            f"preview_columns should be list of 3, got {data['preview_columns']}"
        assert isinstance(data["preview"], list) and len(data["preview"]) <= 5, \
            f"preview should be list of at most 5 rows"

        print(f"PASS: Excel process returned valid response")
        print(f"  message: {data['message']}")
        print(f"  rows: {data['rows']}, columns: {data['columns']}")
        print(f"  preview_columns: {data['preview_columns']}")
        print(f"  download_url: {data['download_url']}")
        return data

    def test_excel_process_missing_file(self, auth_headers):
        """Should return 422 when file is missing"""
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            data={"instruction": "Rename columns"}
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("PASS: Missing file returns 422")

    def test_excel_process_missing_instruction(self, auth_headers):
        """Should return 422 when instruction is missing"""
        csv_buf = io.BytesIO(TEST_CSV_CONTENT)
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            files={"file": ("test.csv", csv_buf, "text/csv")}
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("PASS: Missing instruction returns 422")

    def test_excel_process_invalid_file_type(self, auth_headers):
        """Should return 400 for unsupported file types"""
        txt_buf = io.BytesIO(b"hello world")
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            files={"file": ("test.txt", txt_buf, "text/plain")},
            data={"instruction": "Process this"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Unsupported file type returns 400")

    def test_excel_process_file_too_large(self, auth_headers):
        """Should return 400 for files larger than 10MB"""
        large_content = b"a" * (11 * 1024 * 1024)  # 11MB
        large_buf = io.BytesIO(large_content)
        response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            files={"file": ("large.csv", large_buf, "text/csv")},
            data={"instruction": "Process"}
        )
        assert response.status_code == 400, f"Expected 400 for large file, got {response.status_code}"
        print("PASS: File too large returns 400")


class TestExcelDownloadEndpoint:
    """Tests for GET /api/excel/download/{file_id}"""

    def test_download_requires_auth(self):
        """Should return 401/403 without auth"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/excel/download/{fake_id}")
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"
        print("PASS: Download requires authentication")

    def test_download_invalid_file_id(self, auth_headers):
        """Should return 400 for invalid UUID"""
        response = requests.get(
            f"{BASE_URL}/api/excel/download/not-a-valid-uuid",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Invalid file ID returns 400")

    def test_download_nonexistent_file(self, auth_headers):
        """Should return 404 for valid UUID that doesn't exist"""
        fake_uuid = "11111111-2222-3333-4444-555555555555"
        response = requests.get(
            f"{BASE_URL}/api/excel/download/{fake_uuid}",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: Nonexistent file returns 404")

    def test_full_process_and_download_flow(self, auth_headers):
        """Full flow: process CSV → download xlsx → verify file deleted"""
        # Step 1: Process CSV
        csv_buf = io.BytesIO(TEST_CSV_CONTENT)
        process_response = requests.post(
            f"{BASE_URL}/api/chats/{TEST_CHAT_ID}/excel-process",
            headers=auth_headers,
            files={"file": ("test.csv", csv_buf, "text/csv")},
            data={"instruction": "Translate column names to Russian"}
        )
        assert process_response.status_code == 200, f"Process failed: {process_response.text[:200]}"
        result = process_response.json()
        download_url = result["download_url"]
        file_id = download_url.split("/")[-1]
        print(f"PASS: CSV processed, file_id={file_id}")

        # Step 2: Download the file
        download_response = requests.get(
            f"{BASE_URL}{download_url}",
            headers=auth_headers
        )
        assert download_response.status_code == 200, f"Download failed: {download_response.status_code} - {download_response.text[:200]}"
        content_type = download_response.headers.get("content-type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type or "application/octet-stream" in content_type, \
            f"Expected xlsx content-type, got: {content_type}"
        assert len(download_response.content) > 0, "Downloaded file is empty"
        print(f"PASS: File downloaded successfully ({len(download_response.content)} bytes)")

        # Step 3: Verify file is deleted after download (should return 404)
        second_download = requests.get(
            f"{BASE_URL}{download_url}",
            headers=auth_headers
        )
        assert second_download.status_code == 404, \
            f"Expected 404 after first download (file should be deleted), got {second_download.status_code}"
        print("PASS: File deleted after first download (404 on second attempt)")
